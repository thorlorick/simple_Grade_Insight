from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import UniqueConstraint

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(String, primary_key=True)  # subdomain-based tenant ID
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    students = relationship("Student", back_populates="tenant")
    teachers = relationship("Teacher", back_populates="tenant")
    assignments = relationship("Assignment", back_populates="tenant")
    grades = relationship("Grade", back_populates="tenant")


class Student(Base):
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="students")
    grades = relationship("Grade", back_populates="student")

    # Composite unique constraint on email + tenant_id
    __table_args__ = (
        UniqueConstraint("email", "tenant_id", name="uq_student_email_tenant"),
        {"schema": None},
    )


class Teacher(Base):
    __tablename__ = "teachers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="teachers")
    grades = relationship("Grade", back_populates="teacher")


class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    max_points = Column(Float, nullable=False, default=100.0)
    date = Column(DateTime, nullable=True)  # Assignment due date or creation date
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment")


class Grade(Base):
    __tablename__ = "grades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    score = Column(Float, nullable=False)
    class_tag = Column(String, nullable=True)  # For organizing by class/section
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="grades")
    teacher = relationship("Teacher", back_populates="grades")
    assignment = relationship("Assignment", back_populates="grades")
    tenant = relationship("Tenant", back_populates="grades")

    # Composite unique constraint to prevent duplicate grades for same student/assignment/tenant
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "assignment_id",
            "tenant_id",
            name="uq_student_assignment_tenant"
        ),
        {"schema": None},
    )


# Many-to-many relationship table for assignments and tags
assignment_tags = Table(
    'assignment_tags',
    Base.metadata,
    Column('assignment_id', Integer, ForeignKey('assignments.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class Tag(Base):
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    tenant_id = Column(String(100), nullable=False)
    
    # Many-to-many relationship with assignments
    assignments = relationship("Assignment", secondary=assignment_tags, back_populates="tags")
    
    def __repr__(self):
        return f"<Tag(name='{self.name}')>"

# Also add this to your existing Assignment model:
# Add this relationship to your Assignment class:
# tags = relationship("Tag", secondary=assignment_tags, back_populates="assignments")
