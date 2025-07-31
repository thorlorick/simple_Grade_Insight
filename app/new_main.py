import io
import os
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import traceback
from datetime import datetime, date

from fastapi import FastAPI, UploadFile, File, Depends, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from database import Base, engine, SessionLocal
from models import Student, Assignment, Grade
from downloadTemplate import router as downloadTemplate_router


class GradeInsightApp:
    """Main application class for Grade Insight"""
    
    def __init__(self):
        self.app = FastAPI(title="Grade Insight", version="1.0.0")
        self.templates = None
        self._setup_directories()
        self._setup_templates_and_static()
        self._setup_database()
        self._setup_routes()
    
    def _setup_directories(self) -> None:
        """Ensure required directories exist"""
        for directory in ["templates", "static"]:
            if not os.path.exists(directory):
                os.makedirs(directory)
    
    def _setup_templates_and_static(self) -> None:
        """Setup Jinja2 templates and static files"""
        self.templates = Jinja2Templates(directory="templates")
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
    
    def _setup_database(self) -> None:
        """Initialize database tables with error handling"""
        try:
            Base.metadata.create_all(bind=engine)
            print("Database tables created successfully")
        except Exception as e:
            print(f"Error creating database tables: {e}")
    
    def _setup_routes(self) -> None:
        """Register all application routes"""
        # Include external routers
        self.app.include_router(downloadTemplate_router)
        
        # Register route handlers
        self._register_basic_routes()
        self._register_upload_routes()
        self._register_api_routes()
        self._register_page_routes()
        self._register_utility_routes()
    
    def _register_basic_routes(self) -> None:
        """Register basic navigation routes"""
        @self.app.get("/")
        async def root():
            return RedirectResponse(url="/dashboard")
    
    def _register_upload_routes(self) -> None:
        """Register file upload related routes"""
        @self.app.get("/upload", response_class=HTMLResponse)
        async def upload_form():
            return self._get_upload_form_html()
        
        @self.app.post("/upload")
        async def handle_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
            return await self._handle_file_upload(file, db)
    
    def _register_api_routes(self) -> None:
        """Register API endpoints"""
        @self.app.get("/view-students")
        def view_students(db: Session = Depends(get_db)):
            return self._get_students_simple(db)
        
        @self.app.get("/view-grades")
        def view_grades(db: Session = Depends(get_db)):
            return self._get_students_with_grades(db)
        
        @self.app.get("/api/grades-table")
        def get_grades_for_table(db: Session = Depends(get_db)):
            return self._get_students_with_grades(db)
        
        @self.app.get("/api/students")
        def get_students_list(db: Session = Depends(get_db)):
            return self._get_students_with_stats(db)
        
        @self.app.get("/api/student/{email}")
        def get_student_by_email(email: str, db: Session = Depends(get_db)):
            return self._get_student_details(email, db)
        
        @self.app.get("/api/search-students")
        def search_students(query: str = "", db: Session = Depends(get_db)):
            return self._search_students(query, db)
        
        @self.app.get("/api/assignments")
        def get_assignments(db: Session = Depends(get_db)):
            return self._get_assignments(db)
    
    def _register_page_routes(self) -> None:
        """Register HTML page routes"""
        @self.app.get("/dashboard", response_class=HTMLResponse)
        async def dashboard(request: Request):
            return self._render_template("dashboard.html", request)
        
        @self.app.get("/students", response_class=HTMLResponse)
        async def students_page(request: Request):
            return self._render_template("students.html", request)
        
        @self.app.get("/student-portal", response_class=HTMLResponse)
        async def student_portal(request: Request):
            return self._render_template("student-portal.html", request)
        
        @self.app.get("/teacher-student-view", response_class=HTMLResponse)
        async def teacher_student_view(request: Request):
            return self._render_template("teacher-student-view.html", request)
    
    def _register_utility_routes(self) -> None:
        """Register utility routes"""
        @self.app.get("/reset-db")
        def reset_db():
            return self._reset_database()
        
        @self.app.get("/health")
        def health_check():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    def _render_template(self, template_name: str, request: Request) -> HTMLResponse:
        """Render template with error handling"""
        try:
            return self.templates.TemplateResponse(template_name, {"request": request})
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Error loading {template_name}: {str(e)}"
            )
    
    def _get_upload_form_html(self) -> str:
        """Return the upload form HTML"""
        return """
        <html>
            <head>
                <title>Upload CSV</title>
            </head>
            <body>
                <h1>Upload CSV File</h1>
                <form id="uploadForm">
                    <input id="fileInput" name="file" type="file" accept=".csv" required>
                    <input type="submit" value="Upload">
                </form>

                <div id="loadingMessage" style="display:none; margin-top:1rem; font-weight:bold;">
                    Uploading... please wait.
                </div>

                <script>
                    const form = document.getElementById('uploadForm');
                    const loadingMessage = document.getElementById('loadingMessage');
                    const fileInput = document.getElementById('fileInput');

                    form.addEventListener('submit', async function(event) {
                        event.preventDefault();
                        loadingMessage.style.display = 'block';

                        const formData = new FormData();
                        formData.append('file', fileInput.files[0]);

                        try {
                            const response = await fetch('/upload', {
                                method: 'POST',
                                body: formData,
                            });
                            if (!response.ok) throw new Error('Upload failed');
                            window.location.href = '/dashboard';
                        } catch (err) {
                            loadingMessage.textContent = 'Upload failed. Please try again.';
                        }
                    });
                </script>
            </body>
        </html>
        """
    
    async def _handle_file_upload(self, file: UploadFile, db: Session) -> Dict[str, Any]:
        """Handle CSV file upload with comprehensive error handling"""
        try:
            # Validate file type
            if not file.filename.endswith('.csv'):
                raise HTTPException(status_code=400, detail="Only CSV files are allowed")
            
            # Read and parse CSV
            df = await self._read_csv_file(file)
            print(f"DEBUG: CSV loaded successfully with shape: {df.shape}")
            
            if df.empty:
                raise HTTPException(status_code=400, detail="CSV file is empty")
            
            # Process the CSV data
            upload_result = await self._process_csv_data(df, db)
            db.commit()
            
            print("DEBUG: Upload committed successfully")
            return upload_result
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"DEBUG: Unexpected error in upload: {e}")
            print(traceback.format_exc())
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    async def _read_csv_file(self, file: UploadFile) -> pd.DataFrame:
        """Read CSV file with encoding fallback"""
        contents = await file.read()
        print(f"DEBUG: File received: {file.filename}")
        
        try:
            csv_io = io.StringIO(contents.decode("utf-8"))
            return pd.read_csv(csv_io, header=0)
        except UnicodeDecodeError:
            csv_io = io.StringIO(contents.decode("latin-1"))
            return pd.read_csv(csv_io, header=0)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading CSV file: {str(e)}")
    
    async def _process_csv_data(self, df: pd.DataFrame, db: Session) -> Dict[str, Any]:
        """Process CSV data and update database"""
        if len(df) < 4:
            raise HTTPException(status_code=400, detail="CSV must have at least 4 rows")
        
        # Clean column names and extract metadata
        df.columns = [str(col).strip() for col in df.columns]
        metadata = self._extract_csv_metadata(df)
        
        # Validate and process assignments
        valid_assignments, skipped_assignments = self._validate_assignments(
            metadata['assignment_columns'], metadata['points_row'], len(metadata['student_df'])
        )
        
        if not valid_assignments:
            return self._create_error_response(metadata, skipped_assignments)
        
        # Process students and grades
        processed_students = self._process_students_and_grades(
            metadata['student_df'], valid_assignments, metadata, db
        )
        
        return self._create_success_response(
            file.filename, metadata, valid_assignments, skipped_assignments, processed_students
        )
    
    def _extract_csv_metadata(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract metadata from CSV structure"""
        if len(df.columns) < 3:
            raise HTTPException(status_code=400, detail="CSV must have at least 3 columns")
        
        date_row = df.iloc[0] if len(df) > 1 else None
        points_row = df.iloc[1] if len(df) > 2 else None
        student_df = df.iloc[2:].reset_index(drop=True)
        
        original_columns = df.columns.tolist()
        assignment_columns = original_columns[3:]  # Skip first 3 columns (student info)
        
        # Rename columns for easier processing
        new_column_names = ['last_name', 'first_name', 'email'] + assignment_columns
        student_df.columns = new_column_names
        
        # Validate required columns
        required_columns = {'last_name', 'first_name', 'email'}
        if not required_columns.issubset(student_df.columns):
            missing = required_columns - set(student_df.columns)
            raise HTTPException(status_code=400, detail=f"Missing columns: {list(missing)}")
        
        return {
            'date_row': date_row,
            'points_row': points_row,
            'student_df': student_df,
            'assignment_columns': assignment_columns,
            'original_columns': original_columns
        }
    
    def _validate_assignments(self, assignment_columns: List[str], points_row: pd.Series, 
                            total_students: int) -> Tuple[List[str], List[str]]:
        """Validate which assignments have sufficient data"""
        valid_assignments = []
        skipped_assignments = []
        threshold = max(1, int(total_students * 0.1))
        
        for i, assignment_name in enumerate(assignment_columns):
            col_index = i + 3  # +3 because first 3 are student info
            
            try:
                # Check max points
                max_points_val = None
                if points_row is not None and col_index < len(points_row):
                    max_points_val = points_row.iloc[col_index]
                
                if pd.isna(max_points_val) or str(max_points_val).strip() == '':
                    print(f"DEBUG: Skipping assignment '{assignment_name}' - no max points defined")
                    skipped_assignments.append(assignment_name)
                    continue
                
                try:
                    max_points_val = float(max_points_val)
                    print(f"DEBUG: Assignment '{assignment_name}' has max points: {max_points_val}")
                except (ValueError, TypeError):
                    print(f"DEBUG: Skipping assignment '{assignment_name}' - invalid max points")
                    skipped_assignments.append(assignment_name)
                    continue
                
                # For now, we'll add all assignments with valid max points
                # The actual grade validation will happen during processing
                valid_assignments.append(assignment_name)
                
            except Exception as e:
                print(f"DEBUG: Error validating assignment '{assignment_name}': {e}")
                skipped_assignments.append(assignment_name)
        
        return valid_assignments, skipped_assignments
    
    def _process_students_and_grades(self, student_df: pd.DataFrame, valid_assignments: List[str],
                                   metadata: Dict[str, Any], db: Session) -> int:
        """Process students and their grades"""
        processed_students = 0
        
        for index, row in student_df.iterrows():
            email = str(row['email']).strip().lower()
            if not email or email == 'nan':
                print(f"DEBUG: Skipping row {index} - invalid email")
                continue
            
            processed_students += 1
            
            # Create or update student
            student = self._create_or_update_student(row, email, db)
            
            # Process grades for valid assignments
            self._process_student_grades(
                student, row, valid_assignments, metadata, db
            )
        
        return processed_students
    
    def _create_or_update_student(self, row: pd.Series, email: str, db: Session) -> Student:
        """Create or update student record"""
        student = db.query(Student).filter_by(email=email).first()
        if student:
            student.first_name = str(row['first_name']).strip()
            student.last_name = str(row['last_name']).strip()
        else:
            student = Student(
                email=email,
                first_name=str(row['first_name']).strip(),
                last_name=str(row['last_name']).strip()
            )
            db.add(student)
        return student
    
    def _process_student_grades(self, student: Student, row: pd.Series, 
                              valid_assignments: List[str], metadata: Dict[str, Any], 
                              db: Session) -> None:
        """Process grades for a single student"""
        for assignment_name in valid_assignments:
            try:
                # Get and validate score
                score_value = row[assignment_name]
                if pd.isna(score_value) or str(score_value).strip() == '':
                    continue
                
                try:
                    score = float(score_value)
                except (ValueError, TypeError):
                    print(f"DEBUG: Invalid score '{score_value}' for {student.email}, {assignment_name}")
                    continue
                
                # Get assignment metadata
                assignment_metadata = self._get_assignment_metadata(
                    assignment_name, metadata
                )
                
                # Find or create assignment
                assignment = self._find_or_create_assignment(
                    assignment_name, assignment_metadata, db
                )
                
                # Create or update grade
                self._create_or_update_grade(
                    student.email, assignment.id, score, db
                )
                
            except Exception as e:
                print(f"DEBUG: Error processing grade for {student.email}, {assignment_name}: {e}")
                continue
    
    def _get_assignment_metadata(self, assignment_name: str, 
                               metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract assignment metadata (date, max_points)"""
        assignment_index = metadata['assignment_columns'].index(assignment_name)
        original_col_index = assignment_index + 3
        
        # Get assignment date
        assignment_date = None
        if metadata['date_row'] is not None and original_col_index < len(metadata['date_row']):
            date_val = metadata['date_row'].iloc[original_col_index]
            if pd.notna(date_val) and str(date_val).strip() != '':
                try:
                    parsed_date = pd.to_datetime(date_val, errors='coerce')
                    if pd.notna(parsed_date):
                        assignment_date = parsed_date.date()
                except:
                    pass
        
        # Get max points
        max_points = 100  # default
        if metadata['points_row'] is not None and original_col_index < len(metadata['points_row']):
            try:
                max_val = metadata['points_row'].iloc[original_col_index]
                if pd.notna(max_val) and str(max_val).strip() != '':
                    max_points = float(max_val)
            except (ValueError, TypeError):
                pass
        
        return {
            'date': assignment_date,
            'max_points': max_points
        }
    
    def _find_or_create_assignment(self, name: str, metadata: Dict[str, Any], 
                                 db: Session) -> Assignment:
        """Find existing assignment or create new one"""
        if metadata['date'] is None:
            assignment = db.query(Assignment).filter(
                and_(Assignment.name == name, Assignment.date.is_(None))
            ).first()
        else:
            assignment = db.query(Assignment).filter_by(
                name=name, date=metadata['date']
            ).first()
        
        if not assignment:
            assignment = Assignment(
                name=name,
                date=metadata['date'],
                max_points=metadata['max_points']
            )
            db.add(assignment)
            db.flush()  # Get the ID
        
        return assignment
    
    def _create_or_update_grade(self, email: str, assignment_id: int, 
                              score: float, db: Session) -> None:
        """Create or update grade record"""
        grade = db.query(Grade).filter_by(
            email=email, assignment_id=assignment_id
        ).first()
        
        if grade:
            grade.score = score
        else:
            grade = Grade(
                email=email,
                assignment_id=assignment_id,
                score=score
            )
            db.add(grade)
    
    def _create_error_response(self, metadata: Dict[str, Any], 
                             skipped_assignments: List[str]) -> JSONResponse:
        """Create error response for insufficient assignment data"""
        total_students = len(metadata['student_df'])
        return JSONResponse(
            status_code=400,
            content={
                "error": "No assignments have sufficient data",
                "total_students": total_students,
                "threshold": max(1, int(total_students * 0.1)),
                "all_assignments": metadata['assignment_columns'],
                "skipped_assignments": skipped_assignments
            }
        )
    
    def _create_success_response(self, filename: str, metadata: Dict[str, Any],
                               valid_assignments: List[str], skipped_assignments: List[str],
                               processed_students: int) -> Dict[str, Any]:
        """Create success response for file upload"""
        total_students = len(metadata['student_df'])
        return {
            "status": f"File {filename} uploaded and processed successfully",
            "total_students": total_students,
            "processed_students": processed_students,
            "total_assignments_found": len(metadata['assignment_columns']),
            "valid_assignments": valid_assignments,
            "skipped_assignments": skipped_assignments,
            "processed_assignments": len(valid_assignments),
            "threshold_used": max(1, int(total_students * 0.1))
        }
    
    def _get_students_simple(self, db: Session) -> Dict[str, Any]:
        """Get simple student list"""
        try:
            students = db.query(Student).all()
            result = [
                {
                    "email": s.email,
                    "first_name": s.first_name,
                    "last_name": s.last_name,
                }
                for s in students
            ]
            return {"students": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving students: {str(e)}")
    
    def _get_students_with_grades(self, db: Session) -> Dict[str, Any]:
        """Get students with their grades"""
        try:
            students = db.query(Student).all()
            result = []
            for s in students:
                grades_list = [
                    {
                        "assignment": grade.assignment.name,
                        "date": grade.assignment.date.isoformat() if grade.assignment.date else None,
                        "score": grade.score,
                        "max_points": grade.assignment.max_points,
                    }
                    for grade in s.grades
                ]
                result.append({
                    "email": s.email,
                    "first_name": s.first_name,
                    "last_name": s.last_name,
                    "grades": grades_list,
                })
            return {"students": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving grades: {str(e)}")
    
    def _get_students_with_stats(self, db: Session) -> Dict[str, Any]:
        """Get students with calculated statistics"""
        try:
            students = db.query(Student).all()
            result = []
            for student in students:
                total_grades = len(student.grades)
                total_points = sum(grade.score for grade in student.grades)
                max_possible = sum(grade.assignment.max_points for grade in student.grades)
                avg_percentage = (total_points / max_possible * 100) if max_possible > 0 else 0
                
                result.append({
                    "email": student.email,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "total_assignments": total_grades,
                    "total_points": total_points,
                    "max_possible": max_possible,
                    "average_percentage": round(avg_percentage, 1)
                })
            return {"students": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving students list: {str(e)}")
    
    def _get_student_details(self, email: str, db: Session) -> Dict[str, Any]:
        """Get detailed information for a specific student"""
        student = db.query(Student).filter_by(email=email.lower().strip()).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        grades_list = []
        total_points = 0
        max_possible = 0
        
        for grade in student.grades:
            assignment = grade.assignment
            if assignment:
                score = grade.score or 0
                max_pts = assignment.max_points or 0
                total_points += score
                max_possible += max_pts
                
                grades_list.append({
                    "assignment": assignment.name,
                    "date": assignment.date.isoformat() if assignment.date else None,
                    "score": score,
                    "max_points": max_pts
                })
        
        overall_percentage = (total_points / max_possible * 100) if max_possible > 0 else 0
        
        return {
            "email": student.email,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "total_points": total_points,
            "max_possible": max_possible,
            "overall_percentage": overall_percentage,
            "total_assignments": len(grades_list),
            "grades": grades_list
        }
    
    def _search_students(self, query: str, db: Session) -> Dict[str, Any]:
        """Search students by name or email"""
        try:
            students_query = db.query(Student)
            
            if query.strip():
                search_term = f"%{query.lower()}%"
                students_query = students_query.filter(
                    or_(
                        func.lower(Student.first_name).like(search_term),
                        func.lower(Student.last_name).like(search_term),
                        func.lower(Student.email).like(search_term),
                        func.lower(func.concat(Student.first_name, ' ', Student.last_name)).like(search_term),
                        func.lower(func.concat(Student.last_name, ', ', Student.first_name)).like(search_term)
                    )
                )
            
            students = students_query.all()
            result = []
            
            for student in students:
                grades_list = [
                    {
                        "assignment": grade.assignment.name,
                        "date": grade.assignment.date.isoformat() if grade.assignment.date else None,
                        "max_points": grade.assignment.max_points,
                        "score": grade.score,
                    }
                    for grade in student.grades
                ]
                
                result.append({
                    "email": student.email,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "grades": grades_list,
                })
            
            return {
                "students": result,
                "total_found": len(result),
                "search_query": query
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error searching students: {str(e)}")
    
    def _get_assignments(self, db: Session) -> Dict[str, Any]:
        """Get all assignments with metadata"""
        try:
            assignments = db.query(Assignment).order_by(
                Assignment.date.asc(), Assignment.name.asc()
            ).all()
            
            result = []
            for assignment in assignments:
                grade_count = db.query(Grade).filter_by(assignment_id=assignment.id).count()
                
                result.append({
                    "id": assignment.id,
                    "name": assignment.name,
                    "date": assignment.date.isoformat() if assignment.date else None,
                    "max_points": assignment.max_points,
                    "student_count": grade_count
                })
            
            return {"assignments": result}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving assignments: {str(e)}")
    
    def _reset_database(self) -> Dict[str, str]:
        """Reset the database (drop and recreate all tables)"""
        db = SessionLocal()
        try:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            return {"status": "Database reset successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error resetting database: {str(e)}")
        finally:
            db.close()


def get_db() -> Session:
    """Database dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create the application instance
grade_insight_app = GradeInsightApp()
app = grade_insight_app.app

# For development server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
