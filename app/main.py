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

from app.database import get_db, get_tenant_from_host, engine
from app.models import Grade, Student, Teacher, Assignment, Tenant, Base

app = FastAPI(title="Grade Insight")

# Create tables on startup
def create_tables():
    Base.metadata.create_all(bind=engine)

# Create admin tenant if no tenants exist
def ensure_admin_tenant():
    """Create admin tenant if no tenants exist in database"""
    db = next(get_db())
    try:
        # Check if ANY tenant exists
        tenant_count = db.query(Tenant).count()
        
        if tenant_count == 0:
            # No tenants exist, create admin tenant
            admin_tenant = Tenant(
                id="admin",
                name="Admin Tenant - Default"
            )
            db.add(admin_tenant)
            db.commit()
            print("✅ Created admin tenant (first tenant in database)")
        else:
            print(f"👍 Database already has {tenant_count} tenant(s)")
    
    except Exception as e:
        print(f"❌ Error checking/creating admin tenant: {e}")
        db.rollback()
    finally:
        db.close()

# Initialize on startup
create_tables()
ensure_admin_tenant()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Constants
DEFAULT_MAX_POINTS = 100.0

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Renders the index page.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Renders the dashboard page with grade data.
    Fetches all students along with their grades and related assignment/teacher info.
    """
    students = db.query(models.Student).options(
        joinedload(models.Student.grades).joinedload(models.Grade.assignment).joinedload(models.Assignment.tags),
        joinedload(models.Student.grades).joinedload(models.Grade.teacher)
    ).all()

    # Prepare data for the dashboard to display assignments and grades
    # This logic is kept for dashboard display, assuming 'assignment' on Grade is a string for simplicity
    # but the actual relationship exists.
    
    # Extract unique assignments with their max_points and dates for the header
    assignments_data = {}
    for student in students:
        for grade in student.grades:
            assignment_name = grade.assignment.name # Use the name from the Assignment object
            assignment_date = grade.assignment.date
            assignment_max_points = grade.assignment.max_points
            assignment_tags = [tag.name for tag in grade.assignment.tags] # Extract tag names

            key = (assignment_name, assignment_date, assignment_max_points)
            if key not in assignments_data:
                assignments_data[key] = {
                    'name': assignment_name,
                    'date': assignment_date,
                    'max_points': assignment_max_points,
                    'tags': assignment_tags # Store tags
                }
    
    # Convert to a list and sort by date or name
    sorted_assignments = sorted(
        assignments_data.values(),
        key=lambda x: (x['date'] if x['date'] else datetime.min, x['name'])
    )
    
    # Structure student data for the template
    students_data_for_template = []
    for student in students:
        student_grades_map = {}
        for grade in student.grades:
            # Key grades by a unique identifier for the assignment within the student's context
            assignment_key = (grade.assignment.name, grade.assignment.date, grade.assignment.max_points)
            student_grades_map[assignment_key] = {
                "score": grade.score,
                "max_points": grade.assignment.max_points,
                "assignment": grade.assignment.name,
                "date": grade.assignment.date,
                "tags": [tag.name for tag in grade.assignment.tags] # Add tags here too for student view
            }
        students_data_for_template.append({
            "id": student.id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "email": student.email,
            "grades": student_grades_map
        })

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "students": students_data_for_template,
            "assignments": sorted_assignments,
            "num_students": len(students_data_for_template)
        }
    )


@app.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request, db: Session = Depends(get_db)):
    """
    Renders the CSV upload form page, pre-populating with existing tags.
    """
    tenant_id = "default_tenant" # Placeholder: in a real app, get this from user session/subdomain
    existing_tags = db.query(models.Tag).filter_by(tenant_id=tenant_id).all()
    return templates.TemplateResponse("upload.html", {"request": request, "tags": existing_tags})

@app.post("/upload")
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    teacher_name: str = Form(...),
    class_tag: str = Form(...), # This is used as a string for Grade.class_tag
    tags: Optional[List[int]] = Form(None), # List of existing tag IDs
    new_tags: Optional[str] = Form(None), # Comma-separated new tag names
    db: Session = Depends(get_db)
):
    """
    Handles CSV file upload, parses it, and stores grade data in the database.
    Includes robust error handling and tag integration.
    """
    tenant_id = "default_tenant"  # Placeholder: in a real app, get this from user session/subdomain

    try:
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV file is empty."
        )
    except pd.errors.ParserError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse CSV file. Please check its format."
        )
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode file content. Please ensure it's a valid UTF-8 CSV."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while reading the file: {e}"
        )

    # --- Data Validation (Pre-processing) ---
    required_student_columns = ["First Name", "Last Name", "Email"]
    # Identify potential assignment columns by checking for numeric types later,
    # or assume all other columns are assignments.
    
    # Check for required student columns
    if not all(col in df.columns for col in required_student_columns):
        missing = [col for col in required_student_columns if col not in df.columns]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV is missing required student columns: {', '.join(missing)}. "
                   "Expected 'First Name', 'Last Name', 'Email'."
        )
    
    # Get or create teacher
    teacher = db.query(models.Teacher).filter(
        models.Teacher.name == teacher_name,
        models.Teacher.tenant_id == tenant_id
    ).first()
    if not teacher:
        teacher = models.Teacher(name=teacher_name, tenant_id=tenant_id)
        db.add(teacher)
        db.commit()
        db.refresh(teacher)

    processed_assignments = {} # Cache assignments to avoid duplicate DB queries and creations
    
    # --- Tag Processing ---
    # Fetch existing tags by ID
    assigned_tags_for_assignments = []
    if tags:
        existing_selected_tags = db.query(models.Tag).filter(
            models.Tag.id.in_(tags),
            models.Tag.tenant_id == tenant_id
        ).all()
        assigned_tags_for_assignments.extend(existing_selected_tags)
    
    # Create and add new tags
    if new_tags:
        new_tag_names = [t.strip().lower() for t in new_tags.split(',') if t.strip()]
        for tag_name in new_tag_names:
            if tag_name: # Ensure it's not empty after strip()
                existing_tag = db.query(models.Tag).filter_by(name=tag_name, tenant_id=tenant_id).first()
                if not existing_tag:
                    new_tag_obj = models.Tag(name=tag_name, tenant_id=tenant_id)
                    db.add(new_tag_obj)
                    db.flush() # Flush to get ID if needed later, but relationships handle it
                    assigned_tags_for_assignments.append(new_tag_obj)
                else:
                    assigned_tags_for_assignments.append(existing_tag)
    
    # Remove duplicates from assigned_tags_for_assignments
    # (Important if a new tag name matches an existing selected tag)
    unique_assigned_tags = list({tag.id: tag for tag in assigned_tags_for_assignments}.values())


    # Process each row in the DataFrame
    for index, row in df.iterrows():
        try:
            first_name = row["First Name"]
            last_name = row["Last Name"]
            email = row["Email"]

            # Get or create student
            student = db.query(models.Student).filter(
                models.Student.email == email,
                models.Student.tenant_id == tenant_id
            ).first()
            if not student:
                student = models.Student(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    tenant_id=tenant_id
                )
                db.add(student)
                db.flush() # Flush to get student.id for grades, but don't commit yet

            # Iterate through assignment columns
            for col_name in df.columns:
                if col_name not in required_student_columns:
                    score_value = row[col_name]
                    
                    # Skip if score is NaN or empty (e.g., student didn't take assignment)
                    if pd.isna(score_value) or str(score_value).strip() == '':
                        continue

                    try:
                        score = float(score_value)
                        if score < 0: # Basic score validation
                             raise ValueError("Score cannot be negative.")
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid score '{score_value}' for assignment '{col_name}' "
                                   f"for student {first_name} {last_name}. Score must be a number."
                        )

                    # Get or create assignment
                    # Use a combination of name and tenant_id as a key for caching
                    assignment_cache_key = (col_name, tenant_id)
                    if assignment_cache_key not in processed_assignments:
                        assignment = db.query(models.Assignment).filter(
                            models.Assignment.name == col_name,
                            models.Assignment.tenant_id == tenant_id
                        ).first()
                        if not assignment:
                            assignment = models.Assignment(
                                name=col_name,
                                tenant_id=tenant_id,
                                max_points=DEFAULT_MAX_POINTS, # Default, could be inferred from CSV if needed
                                date=datetime.utcnow() # Default to now, or parse from CSV if column exists
                            )
                            # Add tags to the new assignment
                            for tag_obj in unique_assigned_tags:
                                assignment.tags.append(tag_obj)
                            db.add(assignment)
                            db.flush() # Flush to get assignment.id
                        processed_assignments[assignment_cache_key] = assignment
                    else:
                        assignment = processed_assignments[assignment_cache_key]

                    # Get or update grade
                    grade = db.query(models.Grade).filter(
                        models.Grade.student_id == student.id,
                        models.Grade.assignment_id == assignment.id,
                        models.Grade.tenant_id == tenant_id
                    ).first()

                    if grade:
                        # Update existing grade
                        grade.score = score
                        grade.teacher_id = teacher.id
                        grade.class_tag = class_tag # Update class tag for existing grade
                        grade.updated_at = datetime.utcnow()
                    else:
                        # Create new grade
                        grade = models.Grade(
                            student_id=student.id,
                            teacher_id=teacher.id,
                            assignment_id=assignment.id,
                            tenant_id=tenant_id,
                            score=score,
                            class_tag=class_tag # Set class tag for new grade
                        )
                        db.add(grade)
            db.commit() # Commit after each student's row for better error granularity
        except IntegrityError as e:
            db.rollback()
            # Catch specific unique constraint errors
            if "uq_student_email_tenant" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Duplicate student email '{email}' for tenant '{tenant_id}'. "
                           "Each student email must be unique within a tenant."
                )
            elif "uq_student_assignment_tenant" in str(e):
                 # This should ideally be caught by the .first() and update logic, but as a fallback
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Duplicate grade entry for student {first_name} {last_name} "
                           f"and assignment '{col_name}' for tenant '{tenant_id}'."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error during row {index}: {e}"
                )
        except HTTPException:
            # Re-raise HTTPExceptions from inner validation
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing row {index} (student {first_name} {last_name}): {e}"
            )
    
    return JSONResponse(content={"message": "CSV uploaded and processed successfully!"})

@app.get("/api/grades-table", response_class=JSONResponse)
async def get_grades_table(db: Session = Depends(get_db)):
    """
    API endpoint to fetch structured grade data for the dashboard table.
    """
    students = db.query(models.Student).options(
        joinedload(models.Student.grades).joinedload(models.Grade.assignment).joinedload(models.Assignment.tags),
        joinedload(models.Student.grades).joinedload(models.Grade.teacher)
    ).all()

    students_data = []
    for student in students:
        student_grades = []
        for grade in student.grades:
            student_grades.append({
                "assignment": grade.assignment.name,
                "date": grade.assignment.date.isoformat() if grade.assignment.date else None,
                "max_points": grade.assignment.max_points,
                "score": grade.score,
                "teacher_name": grade.teacher.name,
                "class_tag": grade.class_tag,
                "tags": [tag.name for tag in grade.assignment.tags] # Include actual assignment tags
            })
        students_data.append({
            "id": student.id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "email": student.email,
            "grades": student_grades
        })
    return {"students": students_data}

@app.get("/api/student/{email}", response_class=JSONResponse)
async def get_student_grades(email: str, db: Session = Depends(get_db)):
    """
    API endpoint to fetch a single student's grades by email for the student portal.
    """
    student = db.query(models.Student).filter_by(email=email).options(
        joinedload(models.Student.grades).joinedload(models.Grade.assignment).joinedload(models.Assignment.tags),
        joinedload(models.Student.grades).joinedload(models.Grade.teacher)
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with email {email} not found."
        )

    grades_list = []
    total_assignments = 0
    for grade in student.grades:
        total_assignments += 1
        grades_list.append({
            "assignment": grade.assignment.name,
            "date": grade.assignment.date.isoformat() if grade.assignment.date else None,
            "max_points": grade.assignment.max_points,
            "score": grade.score,
            "teacher_name": grade.teacher.name,
            "class_tag": grade.class_tag,
            "tags": [tag.name for tag in grade.assignment.tags] # Include actual assignment tags
        })
    
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "email": student.email,
        "total_assignments": total_assignments,
        "grades": grades_list
    }

@app.get("/teacher-student-view", response_class=HTMLResponse)
async def teacher_student_view(request: Request, db: Session = Depends(get_db)):
    """
    Renders the teacher's student-specific view.
    """
    return templates.TemplateResponse("teacher_student_view.html", {"request": request})

@app.get("/student-portal", response_class=HTMLResponse)
async def student_portal(request: Request, db: Session = Depends(get_db)):
    """
    Renders the student portal page.
    """
    return templates.TemplateResponse("student-portal.html", {"request": request})
