"""Pydantic schemas for LLM question generation and verification."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GeneratedQuestionLLM(BaseModel):
    """Raw question structure produced by LLM."""

    qtype: str = Field(description="mcq, short_answer, or numerical")
    difficulty: str = Field(description="easy, medium, or hard")
    prompt: str = Field(description="Question stem (max 600 chars)")
    concept_name: Optional[str] = Field(default=None, description="Matching concept name from provided list")
    
    # MCQ fields
    options: Optional[List[str]] = Field(default=None, description="List of exactly 4 plausible option texts")
    correct_option_index: Optional[int] = Field(default=None, description="0-based index of the correct option in options")
    
    # Short-answer fields
    model_answer: Optional[str] = Field(default=None, description="1-3 sentence model response")
    key_points: Optional[List[str]] = Field(default=None, description="2-4 grading rubric key points")
    
    # Numerical fields
    numerical_answer: Optional[float] = Field(default=None, description="Target numerical value")
    unit: Optional[str] = Field(default=None, description="Measurement unit (e.g. m/s^2, kg, Joules)")
    tolerance_pct: Optional[float] = Field(default=5.0, description="Allowed deviation percentage")
    
    # Grounding & explanation
    explanation: str = Field(description="Explanation grounded in cited sources")
    used_sources: List[int] = Field(default_factory=list, description="1-based indices of chunks provided in prompt")


class TopicGenerationLLMOutput(BaseModel):
    """Batch of questions generated for a single topic."""

    questions: List[GeneratedQuestionLLM] = Field(default_factory=list)


class QuestionVerificationItemLLM(BaseModel):
    """Verification results for a single question."""

    question_index: int = Field(description="0-based index of the question in the verification list")
    
    # MCQ verification
    chosen_option_index: Optional[int] = Field(default=None, description="Blindly solved option index 0..3")
    confidence: Optional[float] = Field(default=None, description="Confidence score 0.0 to 1.0")
    
    # Free-response / numerical verification
    supported: bool = Field(description="True if cited sources fully support the question and answer")
    key_correct: Optional[bool] = Field(default=None, description="True if proposed answer key is accurate")
    ambiguous: Optional[bool] = Field(default=False, description="True if question is ambiguous or vague")
    recomputed_value: Optional[float] = Field(default=None, description="Recomputed numerical answer if applicable")
    notes: Optional[str] = Field(default=None, description="Verification notes or reasoning")


class TopicVerificationLLMOutput(BaseModel):
    """Batch verification results for a topic."""

    results: List[QuestionVerificationItemLLM] = Field(default_factory=list)


class CandidateQuestion(BaseModel):
    """Validated in-memory candidate question before final verification and persistence."""

    topic_id: int
    concept_id: Optional[int] = None
    qtype: str
    difficulty: str
    prompt: str
    options: Optional[List[Dict[str, str]]] = None  # [{"key": "A", "text": "..."}]
    correct_answer: str
    explanation: str
    source_chunk_ids: List[int]
    fingerprint: str
    meta: Dict[str, Any] = {}
    verified: bool = False
    verification_notes: Optional[str] = None
    unit: Optional[str] = None
