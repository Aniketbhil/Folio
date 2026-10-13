"""Pydantic schemas for LLM grading and diagnosis outputs."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ShortAnswerGrade(BaseModel):
    """LLM evaluation output for a short answer question."""

    score: float = Field(default=0.0, ge=0.0, le=1.0, description="Score from 0.0 to 1.0")
    key_points_hit: List[str] = Field(default_factory=list, description="List of rubric points addressed")
    key_points_missing: List[str] = Field(default_factory=list, description="List of rubric points omitted")
    feedback: str = Field(description="Constructive student feedback")
    misconception: Optional[str] = Field(default=None, description="One-sentence misconception diagnosis or null")


class WrongAnswerDiagnosis(BaseModel):
    """LLM diagnosis for an incorrect MCQ or numerical question."""

    feedback: str = Field(description="Concise explanation of why student answer is wrong and correct is right")
    misconception: Optional[str] = Field(default=None, description="One-sentence misconception diagnosis or null")


class MisconceptionSummaryItem(BaseModel):
    """Synthesized misconception item."""

    topic_id: int
    text: str
    count: int = 1


class MisconceptionSummary(BaseModel):
    """LLM synthesis output merging assessment misconceptions."""

    items: List[MisconceptionSummaryItem] = Field(default_factory=list)
