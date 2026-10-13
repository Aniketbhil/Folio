"""System metadata and constants endpoint for frontend consumption."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.meta import (
    MetaEnums,
    MetaFeatures,
    MetaLimits,
    MetaResponse,
    MetaThresholds,
)

router = APIRouter(tags=["Metadata"])


@router.get("/meta", response_model=MetaResponse)
def get_metadata() -> MetaResponse:
    """Return application constants, enums, thresholds, limits, and feature flags.

    Provides frontend clients with authoritative system constants without exposing
    internal model names, secrets, or configuration values.
    """
    settings = get_settings()

    enums = MetaEnums(
        source_types=["pdf", "pptx", "video", "video_transcript"],
        source_statuses=["queued", "processing", "ready", "failed"],
        kb_statuses=["empty", "building", "ready", "failed"],
        grounding=["grounded", "partial", "unsupported"],
        assessment_kinds=["practice", "quiz", "mock_exam", "diagnostic"],
        qtypes=["mcq", "short_answer", "numerical"],
        difficulties=["easy", "medium", "hard"],
        mastery_statuses=["new", "weak", "learning", "strong"],
        recommendation_types=[
            "take_diagnostic",
            "practice_topic",
            "review_topic",
            "learn_topic",
            "take_mock_exam",
            "ask_tutor",
        ],
        cta_kinds=["diagnostic", "quiz", "tutor", "source", "mock_exam"],
        activity_kinds=["attempt", "assessment"],
    )

    thresholds = MetaThresholds(
        mastery_weak_below=settings.mastery_weak_below,
        mastery_strong_above=settings.mastery_strong_above,
        review_due_below=settings.review_due_below,
        grade_correct_threshold=settings.grade_correct_threshold,
        tutor_min_score=settings.tutor_min_score,
    )

    limits = MetaLimits(
        max_upload_mb=settings.max_upload_mb,
        quiz_max_questions=settings.quiz_max_questions,
        exam_max_questions=settings.exam_max_questions,
        diagnostic_questions=settings.diagnostic_questions,
        message_max_chars=2000,
        answer_max_chars=4000,
    )

    features = MetaFeatures(
        image_captioning=settings.image_caption_enabled,
        chat_nudges=settings.chat_nudge_enabled,
        tutor_personalization=settings.tutor_personalize,
        llm_mode="mock" if settings.llm_mock else "live",
    )

    return MetaResponse(
        version="0.1.0",
        enums=enums,
        thresholds=thresholds,
        limits=limits,
        features=features,
    )
