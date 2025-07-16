from fastapi import FastAPI, Request, HTTPException, Depends, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc
import pandas as pd
import io
import os
from datetime import datetime

from database import get_db, get_tenant_from_host, engine
from models import Grade, Student, Teacher, Assignment, Tenant, Base

app = FastAPI(title="Grade Insight")

# Create tables on startup
def create_tables():
    Base.metadata.create_all(bind=engine)

create_tables()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    # Get or create tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        tenant = Tenant(id=tenant_id, name=tenant_id.replace("_", " ").title())
        db.add(tenant)
        db.commit()

    students = db.query(Student).filter(Student.tenant_id == tenant_id).all()

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "students": students, "tenant": tenant_id}
    )


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post("/upload")
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    teacher_name: str = Form(...),
    class_tag: str = Form(...),
    db: Session = Depends(get_db)
):
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    # Get or create tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        tenant = Tenant(id=tenant_id, name=tenant_id.replace("_", " ").title())
        db.add(tenant)
        db.commit()

    # Read CSV content
    content = await file.read()
    df = pd.read_csv(io.StringIO(content.decode('utf-8')))

    # Get or create teacher
    teacher = db.query(Teacher).filter(
        Teacher.name == teacher_name,
        Teacher.tenant_id == tenant_id
    ).first()

    if not teacher:
        teacher = Teacher(name=teacher_name, tenant_id=tenant_id)
        db.add(teacher)
        db.commit()
        db.refresh(teacher)

    # Determine assignment columns (exclude 'Last Name', 'First Name', 'Email')
    assignment_columns = [col for col in df.columns if col not in ("Last Name", "First Name", "Email")]

    # Default max points
    DEFAULT_MAX_POINTS = 100.0

    # Cache assignments by name for this tenant to avoid repeated queries
    assignments_cache = {}

    for col in assignment_columns:
        assignment = db.query(Assignment).filter(
            Assignment.name == col,
            Assignment.tenant_id == tenant_id
        ).first()
        if not assignment:
            assignment = Assignment(
                name=col,
                tenant_id=tenant_id,
                max_points=DEFAULT_MAX_POINTS
            )
            db.add(assignment)
            db.commit()
            db.refresh(assignment)
        assignments_cache[col] = assignment

    # Process each row (student)
    for _, row in df.iterrows():
        first_name = row["First Name"]
        last_name = row["Last Name"]
        email = row["Email"]

        # Get or create student by email + tenant
        student = db.query(Student).filter(
            Student.email == email,
            Student.tenant_id == tenant_id
        ).first()

        if not student:
            student = Student(
                first_name=first_name,
                last_name=last_name,
                email=email,
                tenant_id=tenant_id
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        # Create grades for each assignment column
        for assignment_name in assignment_columns:
            score_value = row[assignment_name]
            if pd.isna(score_value):
                continue  # skip if no grade

            assignment = assignments_cache[assignment_name]

            # Check if grade already exists (unique constraint)
            existing_grade = db.query(Grade).filter(
                Grade.student_id == student.id,
                Grade.assignment_id == assignment.id,
                Grade.tenant_id == tenant_id
            ).first()

            if existing_grade:
                # Update existing grade
                existing_grade.score = float(score_value)
                existing_grade.teacher_id = teacher.id
                existing_grade.class_tag = class_tag
            else:
                # New grade
                grade = Grade(
                    student_id=student.id,
                    teacher_id=teacher.id,
                    assignment_id=assignment.id,
                    tenant_id=tenant_id,
                    score=float(score_value),
                    class_tag=class_tag
                )
                db.add(grade)

    db.commit()
    return {"message": "CSV uploaded successfully"}


@app.get("/api/grades-table")
async def get_grades_table(request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    # Get all students for this tenant with their grades
    students = db.query(Student).filter(Student.tenant_id == tenant_id).all()
    
    students_data = []
    for student in students:
        grades = db.query(Grade).filter(
            Grade.student_id == student.id,
            Grade.tenant_id == tenant_id
        ).all()
        
        grades_data = []
        for grade in grades:
            grades_data.append({
                "assignment": grade.assignment.name,
                "date": grade.assignment.date.isoformat() if grade.assignment.date else None,
                "score": grade.score,
                "max_points": grade.assignment.max_points,
                "tags": [grade.class_tag] if grade.class_tag else []
            })
        
        students_data.append({
            "id": student.id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "email": student.email,
            "grades": grades_data
        })
    
    return {"students": students_data}


@app.get("/api/student/{student_id}/grades")
async def get_student_grades(student_id: int, request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_from_host(request.headers.get("host"))

    grades = db.query(Grade).filter(
        Grade.student_id == student_id,
        Grade.tenant_id == tenant_id
    ).all()

    return grades


@app.get("/api/student/{email}")
async def get_student_by_email(email: str, request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    student = db.query(Student).filter(
        Student.email == email,
        Student.tenant_id == tenant_id
    ).first()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    grades = db.query(Grade).filter(
        Grade.student_id == student.id,
        Grade.tenant_id == tenant_id
    ).all()
    
    grades_data = []
    total_points = 0
    max_possible = 0
    
    for grade in grades:
        total_points += grade.score
        max_possible += grade.assignment.max_points
        grades_data.append({
            "assignment": grade.assignment.name,
            "date": grade.assignment.date.isoformat() if grade.assignment.date else None,
            "score": grade.score,
            "max_points": grade.assignment.max_points
        })
    
    overall_percentage = (total_points / max_possible * 100) if max_possible > 0 else 0
    
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "email": student.email,
        "grades": grades_data,
        "total_assignments": len(grades_data),
        "total_points": total_points,
        "max_possible": max_possible,
        "overall_percentage": overall_percentage
    }


@app.get("/api/downloadTemplate")
async def download_template():
    # Create a sample CSV template
    template_data = {
        "Last Name": ["Smith", "Johnson", "Williams"],
        "First Name": ["John", "Jane", "Bob"],
        "Email": ["john.smith@example.com", "jane.johnson@example.com", "bob.williams@example.com"],
        "Assignment 1": [85, 92, 78],
        "Assignment 2": [88, 95, 82],
        "Quiz 1": [90, 88, 85]
    }
    
    df = pd.DataFrame(template_data)
    
    # Create CSV content
    csv_content = df.to_csv(index=False)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=grade_template.csv"
        }
    )


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    total_students = db.query(Student).filter(Student.tenant_id == tenant_id).count()
    total_assignments = db.query(Assignment).filter(Assignment.tenant_id == tenant_id).count()
    total_grades = db.query(Grade).filter(Grade.tenant_id == tenant_id).count()
    
    return {
        "total_students": total_students,
        "total_assignments": total_assignments,
        "total_grades": total_grades
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
