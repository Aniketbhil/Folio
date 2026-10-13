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
    from app.models.topic import ChunkTopic, ChunkConcept


class Source(Base):
    """Source file/document uploaded for a course."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # pdf | pptx | video_transcript
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default="queued", server_default="queued", nullable=False
    )  # queued | processing | ready | failed
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    progress: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    num_units: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    meta: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def media_url(self) -> Optional[str]:
        if self.meta and isinstance(self.meta, dict):
            return self.meta.get("media_url")
        return None

    course: Mapped["Course"] = relationship(back_populates="sources")
    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """Extracted text/content chunk from a source document."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)  # pdf | slide | video
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slide_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    end_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    embedded: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="chunks")
    source: Mapped["Source"] = relationship(back_populates="chunks")
    chunk_topics: Mapped[List["ChunkTopic"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
    chunk_concepts: Mapped[List["ChunkConcept"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
