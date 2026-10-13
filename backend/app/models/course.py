from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.source import Source, Chunk
    from app.models.topic import Topic, Concept
    from app.models.conversation import Conversation
    from app.models.assessment import Assessment, Question


class Course(Base):
    """Course model managing study units, knowledge base state, and relations."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kb_status: Mapped[str] = mapped_column(
        String, default="empty", server_default="empty", nullable=False
    )  # empty | building | ready | failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sources: Mapped[List["Source"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    topics: Mapped[List["Topic"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    concepts: Mapped[List["Concept"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    assessments: Mapped[List["Assessment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    questions: Mapped[List["Question"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
