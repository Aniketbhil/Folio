from typing import Dict, List, Optional
from pydantic import BaseModel


class MetaEnums(BaseModel):
    source_types: List[str]
    source_statuses: List[str]
    kb_statuses: List[str]
    grounding: List[str]
    assessment_kinds: List[str]
    qtypes: List[str]
    difficulties: List[str]
    mastery_statuses: List[str]
    recommendation_types: List[str]
    cta_kinds: List[str]
    activity_kinds: List[str]


class MetaThresholds(BaseModel):
    mastery_weak_below: float
    mastery_strong_above: float
    review_due_below: float
    grade_correct_threshold: float
    tutor_min_score: float


class MetaLimits(BaseModel):
    max_upload_mb: int
    quiz_max_questions: int
    exam_max_questions: int
    diagnostic_questions: int
    message_max_chars: int
    answer_max_chars: int


class MetaFeatures(BaseModel):
    image_captioning: bool
    chat_nudges: bool
    tutor_personalization: bool
    llm_mode: str


class MetaResponse(BaseModel):
    version: str
    enums: MetaEnums
    thresholds: MetaThresholds
    limits: MetaLimits
    features: MetaFeatures
