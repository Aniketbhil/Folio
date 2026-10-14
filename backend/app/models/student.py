from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.assessment import Assessment, Attempt
    from app.models.mastery import Mastery, MasteryEvent


class Student(Base):
    """Student profile model."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    assessments: Mapped[List["Assessment"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    attempts: Mapped[List["Attempt"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    masteries: Mapped[List["Mastery"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    mastery_events: Mapped[List["MasteryEvent"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
