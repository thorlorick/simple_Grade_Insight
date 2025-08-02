# services/csv_processor.py

import csv
import io
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
from utils.database import get_db
from utils.exceptions import ValidationError, ProcessingError
from services.student_service import StudentService
from services.assignment_service import AssignmentService
from models import Student, Assignment, Grade


class CSVProcessor:
    """Service for processing CSV files for grade management"""
    
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
        self.student_service = StudentService(self.db)
        self.assignment_service = AssignmentService(self.db)
    
    def process_students_csv(self, csv_content: str) -> Dict[str, Any]:
        """
        Process CSV file containing student information
        Expected format: email, first_name, last_name, student_number (optional)
        """
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            # Validate headers
            required_headers = {'email', 'first_name', 'last_name'}
            headers = set(csv_reader.fieldnames or [])
            
            if not required_headers.issubset(headers):
                missing = required_headers - headers
                raise ValidationError(f"Missing required headers: {missing}")
            
            created_students = []
            updated_students = []
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    email = row['email'].strip()
                    first_name = row['first_name'].strip()
                    last_name = row['last_name'].strip()
                    student_number = row.get('student_number', '').strip() or None
                    
                    if not email or not first_name or not last_name:
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Check if student exists
                    existing_student = self.student_service.get_student_by_email(email)
                    
                    if existing_student:
                        # Update existing student
                        updated_student = self.student_service.update_student(
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            student_number=student_number
                        )
                        updated_students.append(updated_student)
                    else:
                        # Create new student
                        new_student = self.student_service.create_student(
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            student_number=student_number
                        )
                        created_students.append(new_student)
                
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            return {
                "success": True,
                "created_count": len(created_students),
                "updated_count": len(updated_students),
                "error_count": len(errors),
                "errors": errors,
                "created_students": [s.email for s in created_students],
                "updated_students": [s.email for s in updated_students]
            }
        
        except Exception as e:
            raise ProcessingError(f"Failed to process students CSV: {str(e)}")
    
    def process_assignments_csv(self, csv_content: str) -> Dict[str, Any]:
        """
        Process CSV file containing assignment information
        Expected format: name, max_points, date (optional, format: YYYY-MM-DD)
        """
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            # Validate headers
            required_headers = {'name', 'max_points'}
            headers = set(csv_reader.fieldnames or [])
            
            if not required_headers.issubset(headers):
                missing = required_headers - headers
                raise ValidationError(f"Missing required headers: {missing}")
            
            created_assignments = []
            updated_assignments = []
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    name = row['name'].strip()
                    max_points_str = row['max_points'].strip()
                    date_str = row.get('date', '').strip()
                    
                    if not name or not max_points_str:
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    try:
                        max_points = float(max_points_str)
                    except ValueError:
                        errors.append(f"Row {row_num}: Invalid max_points value")
                        continue
                    
                    assignment_date = None
                    if date_str:
                        try:
                            assignment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        except ValueError:
                            errors.append(f"Row {row_num}: Invalid date format (use YYYY-MM-DD)")
                            continue
                    
                    # Check if assignment exists
                    existing_assignment = self.assignment_service.get_assignment_by_name(name)
                    
                    if existing_assignment:
                        # Update existing assignment
                        updated_assignment = self.assignment_service.update_assignment(
                            assignment_id=existing_assignment.id,
                            max_points=max_points,
                            date=assignment_date
                        )
                        updated_assignments.append(updated_assignment)
                    else:
                        # Create new assignment
                        new_assignment = self.assignment_service.create_assignment(
                            name=name,
                            max_points=max_points,
                            assignment_date=assignment_date
                        )
                        created_assignments.append(new_assignment)
                
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            return {
                "success": True,
                "created_count": len(created_assignments),
                "updated_count": len(updated_assignments),
                "error_count": len(errors),
                "errors": errors,
                "created_assignments": [a.name for a in created_assignments],
                "updated_assignments": [a.name for a in updated_assignments]
            }
        
        except Exception as e:
            raise ProcessingError(f"Failed to process assignments CSV: {str(e)}")
    
    def process_grades_csv(self, csv_content: str) -> Dict[str, Any]:
        """
        Process CSV file containing grade information
        Expected format: student_email, assignment_name, score
        """
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            # Validate headers
            required_headers = {'student_email', 'assignment_name', 'score'}
            headers = set(csv_reader.fieldnames or [])
            
            if not required_headers.issubset(headers):
                missing = required_headers - headers
                raise ValidationError(f"Missing required headers: {missing}")
            
            processed_grades = []
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    student_email = row['student_email'].strip()
                    assignment_name = row['assignment_name'].strip()
                    score_str = row['score'].strip()
                    
                    if not student_email or not assignment_name or not score_str:
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    try:
                        score = float(score_str)
                    except ValueError:
                        errors.append(f"Row {row_num}: Invalid score value")
                        continue
                    
                    # Verify student exists
                    student = self.student_service.get_student_by_email(student_email)
                    if not student:
                        errors.append(f"Row {row_num}: Student not found: {student_email}")
                        continue
                    
                    # Verify assignment exists
                    assignment = self.assignment_service.get_assignment_by_name(assignment_name)
                    if not assignment:
                        errors.append(f"Row {row_num}: Assignment not found: {assignment_name}")
                        continue
                    
                    # Validate score doesn't exceed max points
                    if score > assignment.max_points:
                        errors.append(f"Row {row_num}: Score ({score}) exceeds max points ({assignment.max_points})")
                        continue
                    
                    # Add or update grade
                    grade = self.assignment_service.add_grade_to_assignment(
                        assignment_id=assignment.id,
                        student_email=student_email,
                        score=score
                    )
                    
                    processed_grades.append({
                        "student_email": student_email,
                        "assignment_name": assignment_name,
                        "score": score
                    })
                
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            return {
                "success": True,
                "processed_count": len(processed_grades),
                "error_count": len(errors),
                "errors": errors,
                "processed_grades": processed_grades
            }
        
        except Exception as e:
            raise ProcessingError(f"Failed to process grades CSV: {str(e)}")
    
    def export_students_csv(self) -> str:
        """Export all students to CSV format"""
        students = self.student_service.get_all_students()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['email', 'first_name', 'last_name', 'student_number'])
        
        # Write data
        for student in students:
            writer.writerow([
                student.email,
                student.first_name,
                student.last_name,
                student.student_number or ''
            ])
        
        return output.getvalue()
    
    def export_assignments_csv(self) -> str:
        """Export all assignments to CSV format"""
        assignments = self.assignment_service.get_all_assignments()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['name', 'max_points', 'date'])
        
        # Write data
        for assignment in assignments:
            writer.writerow([
                assignment.name,
                assignment.max_points,
                assignment.date.strftime('%Y-%m-%d') if assignment.date else ''
            ])
        
        return output.getvalue()
    
    def export_grades_csv(self, assignment_id: Optional[int] = None) -> str:
        """Export grades to CSV format"""
        if assignment_id:
            # Export grades for specific assignment
            grades = (self.db.query(Grade, Student, Assignment)
                     .join(Student, Grade.email == Student.email)
                     .join(Assignment, Grade.assignment_id == Assignment.id)
                     .filter(Grade.assignment_id == assignment_id)
                     .all())
        else:
            # Export all grades
            grades = (self.db.query(Grade, Student, Assignment)
                     .join(Student, Grade.email == Student.email)
                     .join(Assignment, Grade.assignment_id == Assignment.id)
                     .all())
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['student_email', 'student_name', 'assignment_name', 'score', 'max_points', 'percentage'])
        
        # Write data
        for grade, student, assignment in grades:
            percentage = (grade.score / assignment.max_points * 100) if grade.score and assignment.max_points > 0 else 0
            writer.writerow([
                student.email,
                f"{student.first_name} {student.last_name}",
                assignment.name,
                grade.score or '',
                assignment.max_points,
                round(percentage, 2)
            ])
        
        return output.getvalue()
    
    def validate_csv_format(self, csv_content: str, expected_type: str) -> Dict[str, Any]:
        """Validate CSV format before processing"""
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            headers = set(csv_reader.fieldnames or [])
            
            format_requirements = {
                'students': {'email', 'first_name', 'last_name'},
                'assignments': {'name', 'max_points'},
                'grades': {'student_email', 'assignment_name', 'score'}
            }
            
            if expected_type not in format_requirements:
                return {"valid": False, "error": "Invalid CSV type"}
            
            required_headers = format_requirements[expected_type]
            
            if not required_headers.issubset(headers):
                missing = required_headers - headers
                return {
                    "valid": False,
                    "error": f"Missing required headers: {missing}",
                    "required_headers": list(required_headers),
                    "found_headers": list(headers)
                }
            
            # Count rows
            row_count = sum(1 for _ in csv_reader)
            
            return {
                "valid": True,
                "headers": list(headers),
                "row_count": row_count,
                "required_headers": list(required_headers)
            }
        
        except Exception as e:
            return {"valid": False, "error": f"CSV parsing error: {str(e)}"}