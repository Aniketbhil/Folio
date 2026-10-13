"""Chat mastery nudges applied after grounded tutor answers."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.mastery import Mastery, MasteryEvent
from app.models.topic import Topic
from app.services.learner.mastery import _get_student_lock

logger = logging.getLogger(__name__)


def apply_chat_nudge(
    db: Session,
    student_id: int,
    topic_ids: List[int],
) -> List[Dict[str, Any]]:
    """Apply a minor mastery bump for the top related leaf topic after a grounded chat turn.

    Rules:
    - Only if CHAT_NUDGE_ENABLED is true.
    - Only for the first valid leaf topic in topic_ids.
    - Lazy creates Mastery row with initial p = BKT_P_INIT, attempts_count = 0, correct_count = 0.
    - Stored p_mastery bumped by CHAT_NUDGE_DELTA up to CHAT_NUDGE_CAP.
    - At most CHAT_NUDGE_MAX_PER_TOPIC_PER_DAY nudges per (student, topic) per UTC day.
    - Writes a MasteryEvent with origin="chat" and attempt_id=None.
    - Thread-safe using the student-level mutex.
    - Caller is responsible for committing inside its transaction.
    """
    settings = get_settings()
    if not settings.chat_nudge_enabled or not topic_ids:
        return []

    # Find the first valid leaf topic
    chosen_topic: Topic | None = None
    for tid in topic_ids:
        topic = db.get(Topic, tid)
        if not topic:
            continue
        # Verify if topic is a leaf topic (no children)
        sub_count = db.scalar(
            select(func.count(Topic.id)).where(Topic.parent_id == tid)
        ) or 0
        if sub_count == 0:
            chosen_topic = topic
            break

    if not chosen_topic:
        return []

    topic_id = chosen_topic.id
    lock = _get_student_lock(student_id)

    with lock:
        # Check daily rate limit per UTC day
        now_utc = datetime.now(timezone.utc)
        day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

        daily_chat_events = db.scalar(
            select(func.count(MasteryEvent.id)).where(
                MasteryEvent.student_id == student_id,
                MasteryEvent.topic_id == topic_id,
                MasteryEvent.origin == "chat",
                MasteryEvent.created_at >= day_start,
            )
        ) or 0

        if daily_chat_events >= settings.chat_nudge_max_per_topic_per_day:
            logger.debug(
                "Chat nudge rate limit reached for student %d topic %d (%d >= %d)",
                student_id,
                topic_id,
                daily_chat_events,
                settings.chat_nudge_max_per_topic_per_day,
            )
            return []

        # Find or initialize Mastery record
        mastery = db.scalar(
            select(Mastery).where(
                Mastery.student_id == student_id,
                Mastery.topic_id == topic_id,
            )
        )

        if not mastery:
            p_before = settings.bkt_p_init
            mastery = Mastery(
                student_id=student_id,
                topic_id=topic_id,
                p_mastery=p_before,
                attempts_count=0,
                correct_count=0,
            )
            db.add(mastery)
        else:
            p_before = mastery.p_mastery

        # Check cap
        if p_before >= settings.chat_nudge_cap:
            return []

        p_after = round(min(p_before + settings.chat_nudge_delta, settings.chat_nudge_cap), 4)
        if p_after <= p_before:
            return []

        # Update mastery (attempts_count, correct_count and last_practiced_at stay unchanged)
        mastery.p_mastery = p_after

        # Record audit event
        event = MasteryEvent(
            student_id=student_id,
            topic_id=topic_id,
            origin="chat",
            p_before=p_before,
            p_after=p_after,
            attempt_id=None,
        )
        db.add(event)

        logger.info(
            "Chat nudge applied: student %d topic %d ('%s') %.4f -> %.4f",
            student_id,
            topic_id,
            chosen_topic.name,
            p_before,
            p_after,
        )

        return [
            {
                "topic": {"id": chosen_topic.id, "name": chosen_topic.name},
                "before": p_before,
                "after": p_after,
            }
        ]
