"""Bayesian Knowledge Tracing (BKT) learner model and mastery tracker."""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.mastery import Mastery, MasteryEvent

logger = logging.getLogger(__name__)

_STUDENT_MASTERY_LOCKS: Dict[int, threading.Lock] = {}
_LOCK_MUTEX = threading.Lock()


def _get_student_lock(student_id: int) -> threading.Lock:
    """Get or create a threading lock for a specific student ID."""
    with _LOCK_MUTEX:
        if student_id not in _STUDENT_MASTERY_LOCKS:
            _STUDENT_MASTERY_LOCKS[student_id] = threading.Lock()
        return _STUDENT_MASTERY_LOCKS[student_id]


def status_for(p_mastery: float, attempts_count: int) -> str:
    """Return mastery status string for a given probability and practice count.

    - "new" if attempts_count == 0
    - "weak" if p_mastery < MASTERY_WEAK_BELOW (default 0.40)
    - "strong" if p_mastery > MASTERY_STRONG_ABOVE (default 0.75)
    - "learning" otherwise
    """
    settings = get_settings()
    if attempts_count == 0:
        return "new"
    if p_mastery < settings.mastery_weak_below:
        return "weak"
    if p_mastery > settings.mastery_strong_above:
        return "strong"
    return "learning"


def bkt_update(p_prior: float, score: float, qtype: str, difficulty: str) -> float:
    """Pure Bayesian Knowledge Tracing update function.

    Args:
        p_prior: Prior mastery probability (0.0 to 1.0)
        score: Fractional score between 0.0 and 1.0 (enables partial credit)
        qtype: "mcq" | "short_answer" | "numerical"
        difficulty: "easy" | "medium" | "hard"

    Returns:
        New mastery probability clamped to [BKT_MIN, BKT_MAX].
    """
    settings = get_settings()

    # Determine guess parameter based on question type
    qt = qtype.lower()
    if qt == "mcq":
        guess = settings.bkt_guess_mcq
    elif qt in {"short_answer", "short"}:
        guess = settings.bkt_guess_short
    elif qt == "numerical":
        guess = settings.bkt_guess_numerical
    else:
        guess = settings.bkt_guess_mcq

    # Determine slip parameter modulated by question difficulty
    diff = difficulty.lower()
    diff_slip_mult = {"easy": 1.5, "medium": 1.0, "hard": 0.6}.get(diff, 1.0)
    slip = settings.bkt_p_slip * diff_slip_mult

    # Clamp prior to safe numerical boundaries
    p = max(settings.bkt_min, min(settings.bkt_max, float(p_prior)))

    # Compute posterior given correct vs wrong response
    p_correct_post = (p * (1.0 - slip)) / ((p * (1.0 - slip)) + ((1.0 - p) * guess))
    p_wrong_post = (p * slip) / ((p * slip) + ((1.0 - p) * (1.0 - guess)))

    # Linear interpolation for partial credit
    s = max(0.0, min(1.0, float(score)))
    posterior = s * p_correct_post + (1.0 - s) * p_wrong_post

    # Transition step: learning transition
    p_new = posterior + (1.0 - posterior) * settings.bkt_p_learn

    # Final clamping
    p_clamped = max(settings.bkt_min, min(settings.bkt_max, p_new))
    return round(p_clamped, 4)


def apply_attempt(
    db: Session,
    student_id: int,
    topic_id: int,
    score: float,
    qtype: str,
    difficulty: str,
    origin: str,
    attempt_id: Optional[int],
    is_correct: bool,
) -> Dict[str, Any]:
    """Apply a student's question attempt to their topic mastery in a single transaction.

    Does NOT commit the database session. Caller is responsible for committing.
    """
    settings = get_settings()
    lock = _get_student_lock(student_id)

    with lock:
        mastery = db.scalar(
            select(Mastery).where(
                Mastery.student_id == student_id,
                Mastery.topic_id == topic_id,
            )
        )
        if not mastery:
            mastery = Mastery(
                student_id=student_id,
                topic_id=topic_id,
                p_mastery=settings.bkt_p_init,
                attempts_count=0,
                correct_count=0,
            )
            db.add(mastery)
            db.flush()

        p_before = mastery.p_mastery
        status_before = status_for(p_before, mastery.attempts_count)

        p_after = bkt_update(p_before, score, qtype, difficulty)
        mastery.p_mastery = p_after
        mastery.attempts_count += 1
        if is_correct:
            mastery.correct_count += 1

        mastery.last_practiced_at = datetime.now(timezone.utc)
        mastery.updated_at = datetime.now(timezone.utc)
        status_after = status_for(p_after, mastery.attempts_count)

        event = MasteryEvent(
            student_id=student_id,
            topic_id=topic_id,
            origin=origin,
            p_before=p_before,
            p_after=p_after,
            attempt_id=attempt_id,
        )
        db.add(event)
        db.flush()

        return {
            "before": p_before,
            "after": p_after,
            "status_before": status_before,
            "status_after": status_after,
            "event_id": event.id,
        }
