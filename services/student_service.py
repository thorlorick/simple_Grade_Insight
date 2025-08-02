# services/student_service.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Student, Grade, Assignment


class StudentService:
    """Service for managing student operations"""
    
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
    
    def create_student(self, email: str, first_name: str, last_name: str, 
                      student_number: Optional[str] = None) -> Student:
        """Create a new student"""
        student = Student(
            email=email,
            first_name=first_name,
            last_name=last_name,
            student_number=student_number
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student
    
    def get_student_by_email(self, email: str) -> Optional[Student]:
        """Get student by email"""
        return self.db.query(Student).filter(Student.email == email).first()
    
    def get_all_students(self) -> List[Student]:
        """Get all students"""
        return self.db.query(Student).all()
    
    def update_student(self, email: str, **kwargs) -> Optional[Student]:
        """Update student information"""
        student = self.get_student_by_email(email)
        if not student:
            return None
        
        for key, value in kwargs.items():
            if hasattr(student, key):
                setattr(student, key, value)
        
        self.db.commit()
        self.db.refresh(student)
        return student
    
    def delete_student(self, email: str) -> bool:
        """Delete a student and all their grades"""
        student = self.get_student_by_email(email)
        if not student:
            return False
        
        # Delete all grades first (cascade should handle this, but being explicit)
        self.db.query(Grade).filter(Grade.email == email).delete()
        self.db.delete(student)
        self.db.commit()
        return True
    
    def get_student_grades(self, email: str) -> List[Grade]:
        """Get all grades for a specific student"""
        return (self.db.query(Grade)
                .filter(Grade.email == email)
                .join(Assignment)
                .all())
    
    def get_student_grade_summary(self, email: str) -> Dict[str, Any]:
        """Get grade summary for a student"""
        grades = (self.db.query(Grade, Assignment)
                 .join(Assignment)
                 .filter(Grade.email == email)
                 .all())
        
        if not grades:
            return {
                "email": email,
                "total_points": 0,
                "earned_points": 0,
                "percentage": 0,
                "grade_count": 0,
                "assignments": []
            }
        
        total_points = sum(assignment.max_points for _, assignment in grades)
        earned_points = sum(grade.score or 0 for grade, _ in grades)
        percentage = (earned_points / total_points * 100) if total_points > 0 else 0
        
        assignments = []
        for grade, assignment in grades:
            assignments.append({
                "assignment_name": assignment.name,
                "assignment_date": assignment.date,
                "max_points": assignment.max_points,
                "score": grade.score,
                "percentage": (grade.score / assignment.max_points * 100) if grade.score and assignment.max_points > 0 else 0
            })
        
        return {
            "email": email,
            "total_points": total_points,
            "earned_points": earned_points,
            "percentage": round(percentage, 2),
            "grade_count": len(grades),
            "assignments": assignments
        }
    
    def bulk_create_students(self, students_data: List[Dict[str, Any]]) -> List[Student]:
        """Create multiple students at once"""
        students = []
        for data in students_data:
            student = Student(**data)
            students.append(student)
        
        self.db.add_all(students)
        self.db.commit()
        
        for student in students:
            self.db.refresh(student)
        
        return students
    
    def search_students(self, search_term: str) -> List[Student]:
        """Search students by name or email"""
        search_pattern = f"%{search_term}%"
        return (self.db.query(Student)
                .filter(
                    (Student.first_name.ilike(search_pattern)) |
                    (Student.last_name.ilike(search_pattern)) |
                    (Student.email.ilike(search_pattern)) |
                    (Student.student_number.ilike(search_pattern))
                )
                .all())
    
    def get_class_statistics(self) -> Dict[str, Any]:
        """Get overall class statistics"""
        total_students = self.db.query(Student).count()
        
        # Get average class performance
        avg_query = (self.db.query(
                        func.avg(Grade.score * 100.0 / Assignment.max_points).label('avg_percentage')
                     )
                     .join(Assignment)
                     .first())
        
        avg_percentage = round(avg_query.avg_percentage or 0, 2)
        
        return {
            "total_students": total_students,
            "average_class_percentage": avg_percentage
        }