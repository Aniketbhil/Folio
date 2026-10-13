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
) -> StudentRead:
    """Get student profile by ID with active course summaries."""
    from sqlalchemy import func
    from app.models.course import Course
    from app.models.mastery import Mastery
    from app.models.topic import Topic
    from app.schemas.student import StudentCourseActivityOut

    student = db.get(Student, student_id)
    if not student:
        raise AppError(
            message=f"Student with id {student_id} not found",
            code="not_found",
            status_code=404,
        )

    active_course_rows = db.execute(
        select(Course.id, Course.name)
        .join(Topic, Topic.course_id == Course.id)
        .join(Mastery, Mastery.topic_id == Topic.id)
        .where(Mastery.student_id == student_id, Mastery.attempts_count > 0)
        .distinct()
    ).all()

    courses_act: List[StudentCourseActivityOut] = []
    for cid, ctitle in active_course_rows:
        m_stats = db.execute(
            select(func.avg(Mastery.p_mastery), func.max(Mastery.last_practiced_at))
            .join(Topic, Topic.id == Mastery.topic_id)
            .where(Mastery.student_id == student_id, Topic.course_id == cid, Mastery.attempts_count > 0)
        ).first()
        courses_act.append(
            StudentCourseActivityOut(
                course_id=cid,
                course_name=ctitle,
                average_mastery=round(float(m_stats[0]), 4) if m_stats and m_stats[0] is not None else None,
                last_active_at=m_stats[1] if m_stats else None,
            )
        )

    return StudentRead(
        id=student.id,
        name=student.name,
        created_at=student.created_at,
        courses_with_activity=courses_act if courses_act else None,
    )
