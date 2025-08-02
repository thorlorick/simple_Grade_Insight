import pandas as pd
import io
import os
import re
import logging
import traceback
import email_validator

from fastapi import FastAPI, Request, HTTPException, Depends, File, UploadFile, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
from fastapi import HTTPException  
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, validator, Field
from contextlib import contextmanager

from app.database import get_db, get_tenant_from_host, engine
from app.models import Grade, Student, Teacher, Assignment, Tenant, Base

from services.student_service import StudentService
from services.assignment_service import AssignmentService
from services.csv_processor import CSVProcessor

app = FastAPI(title="Grade Insight")

# Create tables on startup
def create_tables():
    Base.metadata.create_all(bind=engine)

create_tables()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_or_create_tenant(db: Session, tenant_id: str) -> Tenant:
    """Helper function to get or create tenant"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        tenant = Tenant(id=tenant_id, name=tenant_id.replace("_", " ").title())
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def get_or_create_teacher(db: Session, teacher_name: str, tenant_id: str) -> Teacher:
    """Helper function to get or create teacher"""
    teacher = db.query(Teacher).filter(
        Teacher.name == teacher_name,
        Teacher.tenant_id == tenant_id
    ).first()
    
    if not teacher:
        teacher = Teacher(name=teacher_name, tenant_id=tenant_id)
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
    
    return teacher


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    tenant = get_or_create_tenant(db, tenant_id)
    
    # Use StudentService to get students
    student_service = StudentService(db)
    students = student_service.get_students_by_tenant(tenant_id)

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
    tenant = get_or_create_tenant(db, tenant_id)
    teacher = get_or_create_teacher(db, teacher_name, tenant_id)
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Initialize services
        csv_processor = CSVProcessor(db)
        student_service = StudentService(db)
        assignment_service = AssignmentService(db)
        
        # Process CSV using pandas for the existing format
        df = pd.read_csv(io.StringIO(csv_content))
        
        # Validate required columns
        required_columns = {"Last Name", "First Name", "Email"}
        if not required_columns.issubset(set(df.columns)):
            missing = required_columns - set(df.columns)
            raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")
        
        # Determine assignment columns (exclude student info columns)
        assignment_columns = [col for col in df.columns if col not in ("Last Name", "First Name", "Email")]
        
        if not assignment_columns:
            raise HTTPException(status_code=400, detail="No assignment columns found")
        
        # Default max points
        DEFAULT_MAX_POINTS = 100.0
        
        # Create or get assignments using AssignmentService
        assignments_cache = {}
        for col in assignment_columns:
            assignment = assignment_service.get_assignment_by_name_and_tenant(col, tenant_id)
            if not assignment:
                assignment = assignment_service.create_assignment(
                    name=col,
                    max_points=DEFAULT_MAX_POINTS,
                    tenant_id=tenant_id
                )
            assignments_cache[col] = assignment
        
        # Process each student row
        processed_students = 0
        processed_grades = 0
        
        for _, row in df.iterrows():
            first_name = row["First Name"]
            last_name = row["Last Name"]
            email = row["Email"]
            
            # Get or create student using StudentService
            student = student_service.get_student_by_email_and_tenant(email, tenant_id)
            if not student:
                student = student_service.create_student(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    tenant_id=tenant_id
                )
                processed_students += 1
            
            # Process grades for each assignment column
            for assignment_name in assignment_columns:
                score_value = row[assignment_name]
                if pd.isna(score_value):
                    continue  # skip if no grade
                
                assignment = assignments_cache[assignment_name]
                
                # Check if grade already exists
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
                    # Create new grade
                    grade = Grade(
                        student_id=student.id,
                        teacher_id=teacher.id,
                        assignment_id=assignment.id,
                        tenant_id=tenant_id,
                        score=float(score_value),
                        class_tag=class_tag
                    )
                    db.add(grade)
                    processed_grades += 1
        
        db.commit()
        
        return {
            "message": "CSV uploaded successfully",
            "processed_students": processed_students,
            "processed_grades": processed_grades,
            "assignments_processed": len(assignment_columns)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


@app.get("/api/grades-table")
async def get_grades_table(request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    # Use StudentService to get students with grades
    student_service = StudentService(db)
    students = student_service.get_students_by_tenant(tenant_id)
    
    students_data = []
    for student in students:
        grade_summary = student_service.get_student_grade_summary_by_tenant(student.email, tenant_id)
        
        grades_data = []
        for assignment_data in grade_summary.get("assignments", []):
            grades_data.append({
                "assignment": assignment_data["assignment_name"],
                "date": assignment_data["assignment_date"].isoformat() if assignment_data["assignment_date"] else None,
                "score": assignment_data["score"],
                "max_points": assignment_data["max_points"],
                "tags": []  # Add class tags if needed
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
    
    # Get student and verify tenant
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == tenant_id
    ).first()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Use StudentService to get grade summary
    student_service = StudentService(db)
    grade_summary = student_service.get_student_grade_summary_by_tenant(student.email, tenant_id)
    
    return grade_summary.get("assignments", [])


@app.get("/api/student/{email}")
async def get_student_by_email(email: str, request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    # Use StudentService
    student_service = StudentService(db)
    student = student_service.get_student_by_email_and_tenant(email, tenant_id)
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get comprehensive grade summary
    grade_summary = student_service.get_student_grade_summary_by_tenant(email, tenant_id)
    
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "email": student.email,
        "grades": grade_summary.get("assignments", []),
        "total_assignments": grade_summary.get("grade_count", 0),
        "total_points": grade_summary.get("earned_points", 0),
        "max_possible": grade_summary.get("total_points", 0),
        "overall_percentage": grade_summary.get("percentage", 0)
    }


@app.get("/api/downloadTemplate")
async def download_template():
    """Generate a CSV template for grade uploads"""
    template_data = {
        "Last Name": ["Smith", "Johnson", "Williams"],
        "First Name": ["John", "Jane", "Bob"],
        "Email": ["john.smith@example.com", "jane.johnson@example.com", "bob.williams@example.com"],
        "Assignment 1": [85, 92, 78],
        "Assignment 2": [88, 95, 82],
        "Quiz 1": [90, 88, 85]
    }
    
    df = pd.DataFrame(template_data)
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
    
    # Use services to get statistics
    student_service = StudentService(db)
    assignment_service = AssignmentService(db)
    
    total_students = student_service.get_student_count_by_tenant(tenant_id)
    total_assignments = assignment_service.get_assignment_count_by_tenant(tenant_id)
    total_grades = db.query(Grade).filter(Grade.tenant_id == tenant_id).count()
    
    # Get class statistics
    class_stats = student_service.get_class_statistics_by_tenant(tenant_id)
    
    return {
        "total_students": total_students,
        "total_assignments": total_assignments,
        "total_grades": total_grades,
        "average_class_percentage": class_stats.get("average_class_percentage", 0)
    }


# Additional endpoints using the services

@app.get("/api/assignments")
async def get_assignments(request: Request, db: Session = Depends(get_db)):
    """Get all assignments for the tenant"""
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    assignment_service = AssignmentService(db)
    assignments = assignment_service.get_assignments_by_tenant(tenant_id)
    
    return {"assignments": [
        {
            "id": assignment.id,
            "name": assignment.name,
            "max_points": assignment.max_points,
            "date": assignment.date.isoformat() if assignment.date else None
        }
        for assignment in assignments
    ]}


@app.get("/api/assignments/{assignment_id}/statistics")
async def get_assignment_statistics(assignment_id: int, request: Request, db: Session = Depends(get_db)):
    """Get statistics for a specific assignment"""
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    assignment_service = AssignmentService(db)
    
    # Verify assignment belongs to tenant
    assignment = assignment_service.get_assignment_by_id_and_tenant(assignment_id, tenant_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    statistics = assignment_service.get_assignment_statistics_by_tenant(assignment_id, tenant_id)
    return statistics


@app.post("/api/csv/validate")
async def validate_csv_format(
    file: UploadFile = File(...),
    csv_type: str = Form(...),
    db: Session = Depends(get_db)
):
    """Validate CSV format before processing"""
    content = await file.read()
    csv_content = content.decode('utf-8')
    
    csv_processor = CSVProcessor(db)
    validation_result = csv_processor.validate_csv_format(csv_content, csv_type)
    
    return validation_result


@app.post("/api/csv/process-students")
async def process_students_csv(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Process CSV file containing student information"""
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    content = await file.read()
    csv_content = content.decode('utf-8')
    
    csv_processor = CSVProcessor(db)
    # Note: You'll need to modify CSVProcessor to handle tenant_id
    result = csv_processor.process_students_csv_with_tenant(csv_content, tenant_id)
    
    return result


@app.post("/api/csv/process-assignments")
async def process_assignments_csv(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Process CSV file containing assignment information"""
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    content = await file.read()
    csv_content = content.decode('utf-8')
    
    csv_processor = CSVProcessor(db)
    # Note: You'll need to modify CSVProcessor to handle tenant_id
    result = csv_processor.process_assignments_csv_with_tenant(csv_content, tenant_id)
    
    return result


@app.get("/api/export/students")
async def export_students_csv(request: Request, db: Session = Depends(get_db)):
    """Export students to CSV"""
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    csv_processor = CSVProcessor(db)
    # Note: You'll need to modify CSVProcessor to handle tenant_id
    csv_content = csv_processor.export_students_csv_by_tenant(tenant_id)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=students_export.csv"
        }
    )


@app.get("/api/export/assignments")
async def export_assignments_csv(request: Request, db: Session = Depends(get_db)):
    """Export assignments to CSV"""
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    csv_processor = CSVProcessor(db)
    # Note: You'll need to modify CSVProcessor to handle tenant_id
    csv_content = csv_processor.export_assignments_csv_by_tenant(tenant_id)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=assignments_export.csv"
        }
    )


@app.get("/api/export/grades")
async def export_grades_csv(
    request: Request,
    assignment_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Export grades to CSV"""
    tenant_id = get_tenant_from_host(request.headers.get("host"))
    
    csv_processor = CSVProcessor(db)
    # Note: You'll need to modify CSVProcessor to handle tenant_id
    csv_content = csv_processor.export_grades_csv_by_tenant(tenant_id, assignment_id)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=grades_export_{assignment_id or 'all'}.csv"
        }
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)