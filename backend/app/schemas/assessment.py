from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QuestionOptionOut(BaseModel):
    """Multiple choice question option with letter key and option text."""

    key: str
    text: str


class QuestionTopicOut(BaseModel):
    """Topic reference for a question."""

    id: int
    name: str
    parent_id: Optional[int] = None
    parent_name: Optional[str] = None


class QuestionConceptOut(BaseModel):
    """Concept reference for a question."""

    id: int
    name: str


class QuestionSourceOut(BaseModel):
    """Origin source citation for a question."""

    chunk_id: int
    source_id: int
    source_title: str
    source_type: str
    location: Dict[str, Any]


class QuestionOut(BaseModel):
    """Public question schema returned to students (hiding correct answers when in-progress)."""

    id: int
    position: int
    qtype: str
    difficulty: str
    prompt: str
    options: Optional[List[QuestionOptionOut]] = None
    topic: QuestionTopicOut
    concept: Optional[QuestionConceptOut] = None
    sources: List[QuestionSourceOut] = []
    answered: bool = False
    unit: Optional[str] = None
    # Exposed only when assessment status == "submitted" (Prompt 6+)
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None


class AssessmentCreate(BaseModel):
    """Request payload to create a new assessment."""

    student_id: int
    kind: str = "quiz"  # "quiz" | "mock_exam" | "diagnostic"
    topic_ids: Optional[List[int]] = None
    num_questions: Optional[int] = None
    difficulty: str = "auto"  # "auto" | "easy" | "medium" | "hard"
    question_types: Optional[List[str]] = None  # ["mcq", "short_answer", "numerical"]
    title: Optional[str] = None


class AssessmentOut(BaseModel):
    """Complete assessment details with questions and generation audit report."""

    id: int
    course_id: int
    student_id: int
    kind: str
    status: str
    title: Optional[str] = None
    config: Dict[str, Any] = {}
    num_questions: int
    created_at: datetime
    warnings: List[str] = []
    generation_report: Dict[str, Any] = {}
    questions: List[QuestionOut] = []


class AssessmentListItem(BaseModel):
    """Summary item for assessment listing."""

    id: int
    kind: str
    status: str
    title: Optional[str] = None
    num_questions: int
    answered_count: int = 0
    score: Optional[float] = None
    created_at: datetime
    submitted_at: Optional[datetime] = None


class AssessmentDeleteResponse(BaseModel):
    """Response returned upon assessment deletion."""

    deleted: bool


class DevGenerateQuestionsRequest(BaseModel):
    """Inspection request for /dev/generate-questions."""

    course_id: int
    topic_id: int
    num_questions: int = 3
    difficulty: str = "medium"
    question_types: List[str] = ["mcq", "short_answer"]
    student_id: Optional[int] = None


class DevGenerateQuestionsResponse(BaseModel):
    """Response returned by /dev/generate-questions with full unmasked inspection details."""

    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    mode: str
    verify_model: Optional[str] = None
