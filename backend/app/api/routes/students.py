from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.course import Course
from app.models.mastery import Mastery
from app.models.student import Student
from app.models.topic import Topic
from app.schemas.student import StudentCourseActivityOut, StudentCreate, StudentRead
from app.services.auth.dependencies import get_current_student, require_same_student

router = APIRouter(prefix="/students", tags=["Students"])


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
) -> Student:
    """Create a new student profile (DEBUG only)."""
    settings = get_settings()
    if not settings.debug:
        raise AppError("Not found", code="not_found", status_code=404)

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
    """List all registered students (DEBUG only)."""
    settings = get_settings()
    if not settings.debug:
        raise AppError("Not found", code="not_found", status_code=404)

    stmt = select(Student).order_by(Student.id.asc())
    return list(db.scalars(stmt).all())


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: int,
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> StudentRead:
    """Get student profile by ID with active course summaries (own account only)."""
    require_same_student(current_student, student_id)

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


@router.delete("/{student_id}", response_model=dict)
def delete_student(
    student_id: int,
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> dict:
    """Delete a student and cascade-remove all their conversations, assessments, and mastery records (own account only)."""
    from sqlalchemy import delete
    from app.models.assessment import Assessment, Attempt, Question
    from app.models.conversation import Conversation, Message
    from app.models.mastery import Mastery, MasteryEvent
    from app.services.vector_store import get_vector_store

    require_same_student(current_student, student_id)

    student = db.get(Student, student_id)
    if not student:
        raise AppError(
            message=f"Student with id {student_id} not found",
            code="student_not_found",
            status_code=404,
        )

    # 1. Delete vector store question embeddings for this student's assessments
    assessments = list(
        db.scalars(select(Assessment).where(Assessment.student_id == student_id)).all()
    )
    vstore = get_vector_store()
    for a in assessments:
        vstore.delete_questions_by_assessment(a.id)

    # 2. Delete attempts, questions, assessments
    db.execute(delete(Attempt).where(Attempt.student_id == student_id))
    assessment_ids = [a.id for a in assessments]
    if assessment_ids:
        db.execute(delete(Question).where(Question.assessment_id.in_(assessment_ids)))
    db.execute(delete(Assessment).where(Assessment.student_id == student_id))

    # 3. Delete messages and conversations
    conv_ids = list(
        db.scalars(select(Conversation.id).where(Conversation.student_id == student_id)).all()
    )
    if conv_ids:
        db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
    db.execute(delete(Conversation).where(Conversation.student_id == student_id))

    # 4. Delete mastery events and mastery records
    db.execute(delete(MasteryEvent).where(MasteryEvent.student_id == student_id))
    db.execute(delete(Mastery).where(Mastery.student_id == student_id))

    # 5. Delete student
    db.delete(student)
    db.commit()

    return {"deleted": True}
