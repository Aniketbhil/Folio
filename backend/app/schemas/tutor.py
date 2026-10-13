from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.citation import Citation


class TutorCitation(Citation):
    """Citation with 1-based reference marker number."""

    ref: int


class RelatedTopicItem(BaseModel):
    id: int
    name: str


class ConversationCreate(BaseModel):
    student_id: int
    title: Optional[str] = None


class ConversationRead(BaseModel):
    id: int
    course_id: int
    student_id: int
    title: str
    created_at: datetime
    message_count: int = 0


class ConversationListItem(BaseModel):
    id: int
    course_id: int
    student_id: int
    title: str
    created_at: datetime
    message_count: int = 0
    last_message_preview: Optional[str] = None


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    student_id: int
    topic_ids: Optional[List[int]] = None


class MessageRead(BaseModel):
    id: int
    role: str
    content: str
    grounding: Optional[str] = None
    citations: List[Dict[str, Any]] = []
    outside_knowledge_note: Optional[str] = None
    followups: List[str] = []
    related_topics: List[RelatedTopicItem] = []
    created_at: datetime


class TutorResponse(BaseModel):
    conversation_id: int
    user_message_id: int
    message_id: int
    answer: str
    grounding: Optional[str] = None  # "grounded" | "partial" | "unsupported" | None
    citations: List[TutorCitation] = []
    outside_knowledge_note: Optional[str] = None
    followups: List[str] = []
    related_topics: List[RelatedTopicItem] = []


class ConversationDeleteResponse(BaseModel):
    deleted: bool


class DevAskRequest(BaseModel):
    course_id: int
    question: str
    topic_ids: Optional[List[int]] = None
    history: Optional[List[Dict[str, str]]] = None


class DevAskTopHit(BaseModel):
    chunk_id: int
    score: float
    location: Dict[str, Any]
    snippet: str


class DevAskThresholds(BaseModel):
    min: float
    strong: float


class DevAskResponse(BaseModel):
    rewritten_query: Optional[str] = None
    top_hits: List[DevAskTopHit] = []
    best_score: float = 0.0
    gate: str  # "passed" | "refused_low_score" | "refused_no_content"
    thresholds: DevAskThresholds
    mode: str  # "mock" | "live"
    raw_llm_output: Optional[Dict[str, Any]] = None
    final_response: Dict[str, Any]
