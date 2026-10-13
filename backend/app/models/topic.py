from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.source import Chunk
    from app.models.assessment import Question
    from app.models.mastery import Mastery, MasteryEvent


class Topic(Base):
    """Topic / module within a course syllabus."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="topics")
    parent: Mapped[Optional["Topic"]] = relationship(
        "Topic", remote_side="Topic.id", back_populates="subtopics"
    )
    subtopics: Mapped[List["Topic"]] = relationship(
        "Topic", back_populates="parent"
    )
    concepts: Mapped[List["Concept"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    chunk_topics: Mapped[List["ChunkTopic"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    questions: Mapped[List["Question"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    masteries: Mapped[List["Mastery"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    mastery_events: Mapped[List["MasteryEvent"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class Concept(Base):
    """Specific key concept within a topic."""

    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="concepts")
    topic: Mapped["Topic"] = relationship(back_populates="concepts")
    chunk_concepts: Mapped[List["ChunkConcept"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )


class ChunkTopic(Base):
    """Association between text chunks and topics with relevance weighting."""

    __tablename__ = "chunk_topics"

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    relevance: Mapped[float] = mapped_column(
        Float, default=1.0, server_default="1.0", nullable=False
    )

    chunk: Mapped["Chunk"] = relationship(back_populates="chunk_topics")
    topic: Mapped["Topic"] = relationship(back_populates="chunk_topics")


class ChunkConcept(Base):
    """Association between text chunks and specific concepts."""

    __tablename__ = "chunk_concepts"

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    chunk: Mapped["Chunk"] = relationship(back_populates="chunk_concepts")
    concept: Mapped["Concept"] = relationship(back_populates="chunk_concepts")


class TopicPrereq(Base):
    """Prerequisite relationship between topics within a course."""

    __tablename__ = "topic_prereqs"

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    prereq_topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
