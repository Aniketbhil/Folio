from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.student import Student
    from app.models.topic import Topic, Concept


class Assessment(Base):
    """Quiz, diagnostic test, or mock exam."""

    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(
        String, nullable=False
    )  # diagnostic | quiz | mock_exam
    status: Mapped[str] = mapped_column(
        String, default="in_progress", server_default="in_progress", nullable=False
    )  # in_progress | submitted
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    course: Mapped["Course"] = relationship(back_populates="assessments")
    student: Mapped["Student"] = relationship(back_populates="assessments")
    questions: Mapped[List["Question"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )
    attempts: Mapped[List["Attempt"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class Question(Base):
    """Assessment question linked to syllabus topic and concept."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    qtype: Mapped[str] = mapped_column(
        String, nullable=False
    )  # mcq | short_answer | numerical
    difficulty: Mapped[str] = mapped_column(
        String, nullable=False
    )  # easy | medium | hard
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source_chunk_ids: Mapped[List[Any]] = mapped_column(
        JSON, default=list, nullable=False
    )
    verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String, index=True, nullable=False)
    position: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    meta: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assessment: Mapped["Assessment"] = relationship(back_populates="questions")
    course: Mapped["Course"] = relationship(back_populates="questions")
    topic: Mapped["Topic"] = relationship(back_populates="questions")
    concept: Mapped[Optional["Concept"]] = relationship()
    attempts: Mapped[List["Attempt"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class Attempt(Base):
    """Student attempt and grading for a single question."""

    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    misconception: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    time_taken_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["Student"] = relationship(back_populates="attempts")
    question: Mapped["Question"] = relationship(back_populates="attempts")
    assessment: Mapped["Assessment"] = relationship(back_populates="attempts")
