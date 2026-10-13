from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentRead

router = APIRouter(prefix="/students", tags=["Students"])


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
) -> Student:
    """Create a new student profile."""
    name = payload.name.strip()
    if not name:
        raise AppError(message="Student name cannot be empty", code="validation_error", status_code=422)

    student = Student(name=name)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("", response_model=List[StudentRead])
def list_students(
    db: Session = Depends(get_db),
) -> List[Student]:
    """List all registered students."""
    stmt = select(Student).order_by(Student.id.asc())
    return list(db.scalars(stmt).all())


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
) -> Student:
    """Get student profile by ID."""
    student = db.get(Student, student_id)
    if not student:
        raise AppError(
            message=f"Student with id {student_id} not found",
            code="not_found",
            status_code=404,
        )
    return student
