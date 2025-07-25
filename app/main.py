import pandas as pd
import io
import os
import re
import logging
import email_validator
from fastapi import FastAPI, Request, HTTPException, Depends, File, UploadFile, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, validator, Field
from contextlib import contextmanager

from app.database import get_db, get_tenant_from_host, engine
from app.models import Grade, Student, Teacher, Assignment, Tenant, Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_FILE_TYPES = {'text/csv', 'application/vnd.ms-excel'}
DEFAULT_MAX_POINTS = 100.0
REQUIRED_CSV_COLUMNS = {'Last Name', 'First Name', 'Email'}
MAX_SCORE_MULTIPLIER = 1.5  # Allow scores up to 150% of max points (for extra credit)

# Pydantic models for validation
class GradeResponse(BaseModel):
    assignment: str
    date: Optional[str]
    score: float
    max_points: float
    tags: List[str] = []

class StudentResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    grades: Optional[List[GradeResponse]] = []
    total_assignments: Optional[int] = 0
    total_points: Optional[float] = 0.0
    max_possible: Optional[float] = 0.0
    overall_percentage: Optional[float] = 0.0

class DashboardStats(BaseModel):
    total_students: int
    total_assignments: int
    total_grades: int

class UploadRequest(BaseModel):
    teacher_name: str = Field(..., min_length=1, max_length=100)
    class_tag: str = Field(..., min_length=1, max_length=50)

# Custom exceptions
class ValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

class DatabaseError(HTTPException):
    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

# Utility functions
def validate_email(email: str) -> bool:
    """Validate email format using email-validator library"""
    try:
        email_validator.validate_email(email)
        return True
    except email_validator.EmailNotValidError:
        return False

def validate_name(name: str) -> bool:
    """Validate name contains only letters, spaces, hyphens, and apostrophes"""
    return bool(re.match(r"^[A-Za-z\s\-']+$", name.strip()))

def validate_score(score: float, max_points: float) -> bool:
    """Validate score is within reasonable bounds"""
    return 0 <= score <= (max_points * MAX_SCORE_MULTIPLIER)

def sanitize_string(value: str, max_length: int = 100) -> str:
    """Sanitize string input"""
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()[:max_length]

@contextmanager
def handle_db_errors():
    """Context manager for consistent database error handling"""
    try:
        yield
    except IntegrityError as e:
        logger.error(f"Database integrity error: {e}")
        raise ValidationError("Data integrity constraint violation")
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        raise DatabaseError()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

# Business logic functions
def get_or_create_tenant(db: Session, tenant_id: str) -> Tenant:
    """Get existing tenant or create new one"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        tenant = Tenant(
            id=tenant_id, 
            name=tenant_id.replace("_", " ").replace("-", " ").title()
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant

def get_or_create_teacher(db: Session, teacher_name: str, tenant_id: str) -> Teacher:
    """Get existing teacher or create new one"""
    teacher = db.query(Teacher).filter(
        and_(Teacher.name == teacher_name, Teacher.tenant_id == tenant_id)
    ).first()
    
    if not teacher:
        teacher = Teacher(name=teacher_name, tenant_id=tenant_id)
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
    return teacher

def get_or_create_assignment(db: Session, assignment_name: str, tenant_id: str, max_points: float = DEFAULT_MAX_POINTS) -> Assignment:
    """Get existing assignment or create new one"""
    assignment = db.query(Assignment).filter(
        and_(Assignment.name == assignment_name, Assignment.tenant_id == tenant_id)
    ).first()
    
    if not assignment:
        assignment = Assignment(
            name=assignment_name,
            tenant_id=tenant_id,
            max_points=max_points
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
    return assignment

def get_or_create_student(db: Session, first_name: str, last_name: str, email: str, tenant_id: str) -> Student:
    """Get existing student or create new one"""
    student = db.query(Student).filter(
        and_(Student.email == email, Student.tenant_id == tenant_id)
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
    return student

def validate_csv_structure(df: pd.DataFrame) -> None:
    """Validate CSV has required columns and structure"""
    missing_columns = REQUIRED_CSV_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValidationError(f"Missing required columns: {', '.join(missing_columns)}")
    
    if df.empty:
        raise ValidationError("CSV file is empty")
    
    # Check for assignment columns (any column that's not a required column)
    assignment_columns = [col for col in df.columns if col not in REQUIRED_CSV_COLUMNS]
    if not assignment_columns:
        raise ValidationError("No assignment columns found in CSV")

def process_csv_batch(db: Session, df: pd.DataFrame, teacher: Teacher, class_tag: str, tenant_id: str) -> Dict[str, int]:
    """Process CSV data in batches for better performance"""
    stats = {"students_processed": 0, "grades_created": 0, "grades_updated": 0, "errors": 0}
    
    # Get assignment columns
    assignment_columns = [col for col in df.columns if col not in REQUIRED_CSV_COLUMNS]
    
    # Pre-create all assignments to avoid repeated queries
    assignments_cache = {}
    for col in assignment_columns:
        assignments_cache[col] = get_or_create_assignment(db, col, tenant_id)
    
    # Process each row
    for index, row in df.iterrows():
        try:
            # Validate and sanitize student data
            first_name = sanitize_string(row["First Name"], 50)
            last_name = sanitize_string(row["Last Name"], 50)
            email = sanitize_string(row["Email"], 100)
            
            if not first_name or not last_name or not email:
                logger.warning(f"Skipping row {index + 1}: Missing required student data")
                stats["errors"] += 1
                continue
                
            if not validate_email(email):
                logger.warning(f"Skipping row {index + 1}: Invalid email {email}")
                stats["errors"] += 1
                continue
                
            if not validate_name(first_name) or not validate_name(last_name):
                logger.warning(f"Skipping row {index + 1}: Invalid name format")
                stats["errors"] += 1
                continue
            
            # Get or create student
            student = get_or_create_student(db, first_name, last_name, email, tenant_id)
            stats["students_processed"] += 1
            
            # Process grades for this student
            for assignment_name in assignment_columns:
                score_value = row[assignment_name]
                
                if pd.isna(score_value) or score_value == '':
                    continue  # Skip empty grades
                
                try:
                    score = float(score_value)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid score '{score_value}' for {student.email} in {assignment_name}")
                    stats["errors"] += 1
                    continue
                
                assignment = assignments_cache[assignment_name]
                
                # Validate score
                if not validate_score(score, assignment.max_points):
                    logger.warning(f"Invalid score {score} for assignment {assignment_name} (max: {assignment.max_points})")
                    stats["errors"] += 1
                    continue
                
                # Check if grade already exists
                existing_grade = db.query(Grade).filter(
                    and_(
                        Grade.student_id == student.id,
                        Grade.assignment_id == assignment.id,
                        Grade.tenant_id == tenant_id
                    )
                ).first()
                
                if existing_grade:
                    # Update existing grade
                    existing_grade.score = score
                    existing_grade.teacher_id = teacher.id
                    existing_grade.class_tag = class_tag
                    existing_grade.updated_at = datetime.utcnow()
                    stats["grades_updated"] += 1
                else:
                    # Create new grade
                    grade = Grade(
                        student_id=student.id,
                        teacher_id=teacher.id,
                        assignment_id=assignment.id,
                        tenant_id=tenant_id,
                        score=score,
                        class_tag=class_tag
                    )
                    db.add(grade)
                    stats["grades_created"] += 1
        
        except Exception as e:
            logger.error(f"Error processing row {index + 1}: {e}")
            stats["errors"] += 1
            continue
    
    return stats

# FastAPI app setup
app = FastAPI(
    title="Grade Insight",
    description="A secure multi-tenant grade management system",
    version="2.0.0"
)

# Create tables on startup
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

create_tables()

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page"""
    try:
        tenant_id = get_tenant_from_host(request.headers.get("host"))
        tenant = get_or_create_tenant(db, tenant_id)
        
        with handle_db_errors():
            students = db.query(Student).filter(Student.tenant_id == tenant_id).all()
        
        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "students": students, "tenant": tenant_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Dashboard temporarily unavailable")

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Upload page for CSV files"""
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload")
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    teacher_name: str = Form(...),
    class_tag: str = Form(...),
    db: Session = Depends(get_db)
):
    """Upload and process CSV file with grades"""
    try:
        tenant_id = get_tenant_from_host(request.headers.get("host"))
        
        # Validate form inputs
        if not teacher_name.strip() or len(teacher_name.strip()) > 100:
            raise ValidationError("Teacher name must be 1-100 characters")
        
        if not class_tag.strip() or len(class_tag.strip()) > 50:
            raise ValidationError("Class tag must be 1-50 characters")
        
        teacher_name = teacher_name.strip()
        class_tag = class_tag.strip()
        
        # Validate file
        if not file.filename:
            raise ValidationError("No file selected")
        
        if not file.filename.endswith('.csv'):
            raise ValidationError("Only CSV files are allowed")
        
        # Read file content with size limit
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise ValidationError(f"File size exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit")
        
        # Parse CSV
        try:
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        except UnicodeDecodeError:
            raise ValidationError("Invalid file encoding. Please use UTF-8 encoded CSV files")
        except pd.errors.EmptyDataError:
            raise ValidationError("CSV file is empty")
        except pd.errors.ParserError as e:
            raise ValidationError(f"CSV parsing error: {str(e)}")
        
        # Validate CSV structure
        validate_csv_structure(df)
        
        with handle_db_errors():
            # Get or create tenant, teacher
            tenant = get_or_create_tenant(db, tenant_id)
            teacher = get_or_create_teacher(db, teacher_name, tenant_id)
            
            # Process CSV data
            stats = process_csv_batch(db, df, teacher, class_tag, tenant_id)
            db.commit()
        
        message = f"CSV processed successfully. Students: {stats['students_processed']}, " \
                 f"Grades created: {stats['grades_created']}, Grades updated: {stats['grades_updated']}"
        
        if stats['errors'] > 0:
            message += f", Errors: {stats['errors']}"
        
        return {"message": message, "stats": stats}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

@app.get("/api/grades-table")
async def get_grades_table(request: Request, db: Session = Depends(get_db)):
    """Get all students and their grades for the tenant"""
    try:
        tenant_id = get_tenant_from_host(request.headers.get("host"))
        
        with handle_db_errors():
            students = db.query(Student).filter(Student.tenant_id == tenant_id).all()
            
            students_data = []
            for student in students:
                grades = db.query(Grade).filter(
                    and_(Grade.student_id == student.id, Grade.tenant_id == tenant_id)
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grades table error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve grades")

@app.get("/api/student/{student_id}/grades")
async def get_student_grades(student_id: int, request: Request, db: Session = Depends(get_db)):
    """Get grades for a specific student"""
    try:
        tenant_id = get_tenant_from_host(request.headers.get("host"))
        
        with handle_db_errors():
            # Verify student belongs to tenant
            student = db.query(Student).filter(
                and_(Student.id == student_id, Student.tenant_id == tenant_id)
            ).first()
            
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")
            
            grades = db.query(Grade).filter(
                and_(Grade.student_id == student_id, Grade.tenant_id == tenant_id)
            ).all()
        
        return [{"id": g.id, "score": g.score, "assignment": g.assignment.name, 
                "max_points": g.assignment.max_points} for g in grades]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Student grades error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve student grades")

@app.get("/api/student/{email}")
async def get_student_by_email(email: str, request: Request, db: Session = Depends(get_db)):
    """Get student details and grades by email"""
    try:
        tenant_id = get_tenant_from_host(request.headers.get("host"))
        
        if not validate_email(email):
            raise ValidationError("Invalid email format")
        
        with handle_db_errors():
            student = db.query(Student).filter(
                and_(Student.email == email, Student.tenant_id == tenant_id)
            ).first()
            
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")
            
            grades = db.query(Grade).filter(
                and_(Grade.student_id == student.id, Grade.tenant_id == tenant_id)
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
        
        return StudentResponse(
            id=student.id,
            first_name=student.first_name,
            last_name=student.last_name,
            email=student.email,
            grades=grades_data,
            total_assignments=len(grades_data),
            total_points=total_points,
            max_possible=max_possible,
            overall_percentage=overall_percentage
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Student lookup error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve student")

@app.get("/api/downloadTemplate")
async def download_template():
    """Download CSV template file"""
    try:
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
                "Content-Disposition": "attachment; filename=grade_template.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
    except Exception as e:
        logger.error(f"Template download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate template")

@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(request: Request, db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    try:
        tenant_id = get_tenant_from_host(request.headers.get("host"))
        
        with handle_db_errors():
            total_students = db.query(Student).filter(Student.tenant_id == tenant_id).count()
            total_assignments = db.query(Assignment).filter(Assignment.tenant_id == tenant_id).count()
            total_grades = db.query(Grade).filter(Grade.tenant_id == tenant_id).count()
        
        return DashboardStats(
            total_students=total_students,
            total_assignments=total_assignments,
            total_grades=total_grades
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        with SessionLocal() as db:
            db.execute("SELECT 1")
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle validation errors consistently"""
    return {"error": exc.detail, "status_code": exc.status_code}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8081,
        log_level="info",
        access_log=True
    )
