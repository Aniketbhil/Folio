from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.course import Course
from app.models.source import Chunk, Source
from app.models.topic import Concept, Topic
from app.schemas.course import (
    CourseCounts,
    CourseCreate,
    CourseDeleteResponse,
    CourseDetailRead,
    CourseRead,
)
from app.services.course_service import delete_course

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
) -> Course:
    """Create a new course."""
    name = payload.name.strip()
    if not name:
        raise AppError(message="Course name cannot be empty", code="validation_error", status_code=422)

    course = Course(
        name=name,
        description=payload.description.strip() if payload.description else None,
        kb_status="empty",
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("", response_model=List[CourseRead])
def list_courses(
    db: Session = Depends(get_db),
) -> List[Course]:
    """List all courses."""
    stmt = select(Course).order_by(Course.id.asc())
    return list(db.scalars(stmt).all())


@router.get("/{course_id}", response_model=CourseDetailRead)
def get_course_detail(
    course_id: int,
    db: Session = Depends(get_db),
) -> CourseDetailRead:
    """Get detailed course information including counts of knowledge base items."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            message=f"Course with id {course_id} not found",
            code="not_found",
            status_code=404,
        )

    sources_cnt = (
        db.scalar(
            select(func.count(Source.id)).where(Source.course_id == course_id)
        )
        or 0
    )
    chunks_cnt = (
        db.scalar(
            select(func.count(Chunk.id)).where(Chunk.course_id == course_id)
        )
        or 0
    )
    embedded_cnt = (
        db.scalar(
            select(func.count(Chunk.id)).where(
                Chunk.course_id == course_id, Chunk.embedded == True
            )
        )
        or 0
    )
    topics_cnt = (
        db.scalar(
            select(func.count(Topic.id)).where(Topic.course_id == course_id)
        )
        or 0
    )
    concepts_cnt = (
        db.scalar(
            select(func.count(Concept.id)).where(Concept.course_id == course_id)
        )
        or 0
    )

    counts = CourseCounts(
        sources=sources_cnt,
        chunks=chunks_cnt,
        embedded_chunks=embedded_cnt,
        topics=topics_cnt,
        concepts=concepts_cnt,
    )

    return CourseDetailRead(
        id=course.id,
        name=course.name,
        description=course.description,
        kb_status=course.kb_status,
        kb_error=course.kb_error,
        kb_built_at=course.kb_built_at,
        created_at=course.created_at,
        counts=counts,
    )


@router.delete("/{course_id}", response_model=CourseDeleteResponse)
def remove_course(
    course_id: int,
    db: Session = Depends(get_db),
) -> CourseDeleteResponse:
    """Cascade delete course, its files, vector embeddings, and database records."""
    delete_course(db=db, course_id=course_id)
    return CourseDeleteResponse(deleted=True)
