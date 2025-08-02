# services/assignment_service.py

from typing import List, Optional, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from utils.database import get_db
from models import Assignment, Grade, Student


class AssignmentService:
    """Service for managing assignment operations"""
    
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
    
    def create_assignment(self, name: str, max_points: float, 
                         assignment_date: Optional[date] = None) -> Assignment:
        """Create a new assignment"""
        assignment = Assignment(
            name=name,
            max_points=max_points,
            date=assignment_date
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment
    
    def get_assignment_by_id(self, assignment_id: int) -> Optional[Assignment]:
        """Get assignment by ID"""
        return self.db.query(Assignment).filter(Assignment.id == assignment_id).first()
    
    def get_assignment_by_name(self, name: str) -> Optional[Assignment]:
        """Get assignment by name"""
        return self.db.query(Assignment).filter(Assignment.name == name).first()
    
    def get_all_assignments(self) -> List[Assignment]:
        """Get all assignments"""
        return self.db.query(Assignment).order_by(Assignment.date.desc()).all()
    
    def update_assignment(self, assignment_id: int, **kwargs) -> Optional[Assignment]:
        """Update assignment information"""
        assignment = self.get_assignment_by_id(assignment_id)
        if not assignment:
            return None
        
        for key, value in kwargs.items():
            if hasattr(assignment, key):
                setattr(assignment, key, value)
        
        self.db.commit()
        self.db.refresh(assignment)
        return assignment
    
    def delete_assignment(self, assignment_id: int) -> bool:
        """Delete an assignment and all associated grades"""
        assignment = self.get_assignment_by_id(assignment_id)
        if not assignment:
            return False
        
        # Delete all grades for this assignment
        self.db.query(Grade).filter(Grade.assignment_id == assignment_id).delete()
        self.db.delete(assignment)
        self.db.commit()
        return True
    
    def get_assignment_grades(self, assignment_id: int) -> List[Grade]:
        """Get all grades for a specific assignment"""
        return (self.db.query(Grade)
                .filter(Grade.assignment_id == assignment_id)
                .join(Student)
                .all())
    
    def get_assignment_statistics(self, assignment_id: int) -> Dict[str, Any]:
        """Get statistics for a specific assignment"""
        assignment = self.get_assignment_by_id(assignment_id)
        if not assignment:
            return {}
        
        grades = (self.db.query(Grade)
                 .filter(Grade.assignment_id == assignment_id)
                 .filter(Grade.score.isnot(None))
                 .all())
        
        if not grades:
            return {
                "assignment_id": assignment_id,
                "assignment_name": assignment.name,
                "max_points": assignment.max_points,
                "submission_count": 0,
                "average_score": 0,
                "average_percentage": 0,
                "highest_score": 0,
                "lowest_score": 0,
                "grades": []
            }
        
        scores = [grade.score for grade in grades if grade.score is not None]
        average_score = sum(scores) / len(scores)
        average_percentage = (average_score / assignment.max_points * 100) if assignment.max_points > 0 else 0
        
        # Get detailed grade information with student names
        detailed_grades = (self.db.query(Grade, Student)
                          .join(Student)
                          .filter(Grade.assignment_id == assignment_id)
                          .all())
        
        grade_details = []
        for grade, student in detailed_grades:
            percentage = (grade.score / assignment.max_points * 100) if grade.score and assignment.max_points > 0 else 0
            grade_details.append({
                "student_email": student.email,
                "student_name": f"{student.first_name} {student.last_name}",
                "score": grade.score,
                "percentage": round(percentage, 2)
            })
        
        return {
            "assignment_id": assignment_id,
            "assignment_name": assignment.name,
            "assignment_date": assignment.date,
            "max_points": assignment.max_points,
            "submission_count": len(scores),
            "average_score": round(average_score, 2),
            "average_percentage": round(average_percentage, 2),
            "highest_score": max(scores),
            "lowest_score": min(scores),
            "grades": grade_details
        }
    
    def get_assignments_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all assignments"""
        assignments = self.get_all_assignments()
        summary = []
        
        for assignment in assignments:
            stats = self.get_assignment_statistics(assignment.id)
            summary.append({
                "id": assignment.id,
                "name": assignment.name,
                "date": assignment.date,
                "max_points": assignment.max_points,
                "submission_count": stats.get("submission_count", 0),
                "average_percentage": stats.get("average_percentage", 0)
            })
        
        return summary
    
    def bulk_create_assignments(self, assignments_data: List[Dict[str, Any]]) -> List[Assignment]:
        """Create multiple assignments at once"""
        assignments = []
        for data in assignments_data:
            assignment = Assignment(**data)
            assignments.append(assignment)
        
        self.db.add_all(assignments)
        self.db.commit()
        
        for assignment in assignments:
            self.db.refresh(assignment)
        
        return assignments
    
    def search_assignments(self, search_term: str) -> List[Assignment]:
        """Search assignments by name"""
        search_pattern = f"%{search_term}%"
        return (self.db.query(Assignment)
                .filter(Assignment.name.ilike(search_pattern))
                .order_by(Assignment.date.desc())
                .all())
    
    def add_grade_to_assignment(self, assignment_id: int, student_email: str, 
                               score: float) -> Optional[Grade]:
        """Add or update a grade for an assignment"""
        # Check if grade already exists
        existing_grade = (self.db.query(Grade)
                         .filter(Grade.assignment_id == assignment_id)
                         .filter(Grade.email == student_email)
                         .first())
        
        if existing_grade:
            existing_grade.score = score
            self.db.commit()
            self.db.refresh(existing_grade)
            return existing_grade
        else:
            # Create new grade
            new_grade = Grade(
                assignment_id=assignment_id,
                email=student_email,
                score=score
            )
            self.db.add(new_grade)
            self.db.commit()
            self.db.refresh(new_grade)
            return new_grade
    
    def get_recent_assignments(self, limit: int = 5) -> List[Assignment]:
        """Get most recent assignments"""
        return (self.db.query(Assignment)
                .order_by(desc(Assignment.date))
                .limit(limit)
                .all())