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


class QuestionAttemptOut(BaseModel):
    """Attempt summary included with answered question."""

    answer: str
    is_correct: bool
    score: float
    feedback: str


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
    attempt: Optional[QuestionAttemptOut] = None
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
    answered_count: int = 0
    score: Optional[float] = None
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


class AnswerSubmitRequest(BaseModel):
    """Request payload for answering an assessment question."""

    answer: str
    time_taken_sec: Optional[float] = None
    student_id: Optional[int] = None


class AnswerMasteryUpdate(BaseModel):
    """Mastery delta for a topic after answering a question."""

    topic: Dict[str, Any]
    before: float
    after: float
    status_before: str
    status_after: str


class AnswerProgress(BaseModel):
    """Progress tracking within an assessment."""

    answered: int
    total: int


class AnswerSubmitResponse(BaseModel):
    """Response returned when submitting an answer."""

    attempt_id: int
    question_id: int
    is_correct: bool
    score: float
    correct_answer: Any
    explanation: str
    feedback: str
    citations: List[Dict[str, Any]] = []
    misconception: Optional[str] = None
    key_points_hit: Optional[List[str]] = None
    key_points_missing: Optional[List[str]] = None
    mastery_update: AnswerMasteryUpdate
    progress: AnswerProgress


class AssessmentReportSummary(BaseModel):
    """Summary section of assessment performance report."""

    score: float
    score_pct: float
    total_questions: int
    answered: int
    correct: int
    skipped: int
    avg_time_sec: Optional[float] = None
    total_time_sec: Optional[float] = None


class AssessmentReportResponse(BaseModel):
    """Comprehensive performance report returned on submit and GET /report."""

    assessment: Dict[str, Any]
    summary: AssessmentReportSummary
    by_topic: List[Dict[str, Any]] = []
    weak_topics: List[Dict[str, Any]] = []
    strong_topics: List[Dict[str, Any]] = []
    by_difficulty: List[Dict[str, Any]] = []
    by_type: List[Dict[str, Any]] = []
    misconceptions: List[Dict[str, Any]] = []
    review: List[Dict[str, Any]] = []
    recommended_next_steps: List[Dict[str, Any]] = []
    diagnostic_note: Optional[str] = None


class DevBktSimulateStep(BaseModel):
    """Input step for BKT simulation."""

    score: float
    qtype: str = "mcq"
    difficulty: str = "medium"


class DevBktSimulateRequest(BaseModel):
    """Request payload for /dev/bkt-simulate."""

    sequence: List[DevBktSimulateStep]
    p_init: Optional[float] = None


class DevBktTrajectoryItem(BaseModel):
    """Single transition step in BKT simulation trajectory."""

    step: int
    score: float
    qtype: str
    difficulty: str
    p_before: float
    p_after: float


class DevBktSimulateResponse(BaseModel):
    """Response payload for /dev/bkt-simulate."""

    trajectory: List[DevBktTrajectoryItem]

