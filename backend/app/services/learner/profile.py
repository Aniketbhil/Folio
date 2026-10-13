"""Student course state loader and profile aggregator.

Performs bulk, bounded SQL queries (O(1) database queries) to load all leaf topic
mastery, forgetting curve decays, trends, prerequisites, and aggregate metrics.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.mastery import Mastery, MasteryEvent
from app.models.student import Student
from app.models.topic import ChunkTopic, Topic, TopicPrereq
from app.services.learner.forgetting import effective_mastery, is_due, retrievability
from app.services.learner.mastery import status_for

logger = logging.getLogger(__name__)


@dataclass
class TopicPrereqState:
    """Prerequisite status for a leaf topic."""

    id: int
    name: str
    satisfied: bool


@dataclass
class LeafTopicState:
    """State of an individual leaf topic for a student."""

    id: int
    name: str
    parent_id: Optional[int]
    parent_name: Optional[str]
    order_index: int
    chunk_count: int
    p_mastery: float
    effective_mastery: float
    retrievability: float
    status: str
    due_for_review: bool
    last_practiced_at: Optional[datetime]
    attempts_count: int
    correct_count: int
    prerequisite_ids: List[int] = field(default_factory=list)
    prerequisites: List[TopicPrereqState] = field(default_factory=list)
    trend: List[float] = field(default_factory=list)
    trend_delta: float = 0.0


@dataclass
class StudentCourseState:
    """Complete learner profile for a student within a specific course."""

    student_id: int
    course_id: int
    student_name: str
    course_name: str
    kb_ready: bool
    needs_diagnostic: bool
    topics: List[LeafTopicState]
    average_mastery: Optional[float]
    readiness: float
    coverage_practiced: int
    coverage_total: int
    counts: Dict[str, int]
    total_attempts: int
    total_correct: int
    overall_accuracy: Optional[float]


def load_student_course_state(
    db: Session,
    student_id: int,
    course_id: int,
    now: Optional[datetime] = None,
    tz_offset_min: int = 0,
) -> StudentCourseState:
    """Load complete student course state using bounded bulk queries.

    Guarantees O(1) database statements regardless of topic count.
    """
    settings = get_settings()

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Fetch Student and Course (validation)
    student = db.get(Student, student_id)
    if not student:
        raise AppError(
            f"Student {student_id} not found",
            code="student_not_found",
            status_code=404,
        )

    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    # 2. Fetch all course topics
    all_topics = db.scalars(
        select(Topic)
        .where(Topic.course_id == course_id)
        .order_by(Topic.order_index.asc(), Topic.id.asc())
    ).all()

    if not all_topics or course.kb_status != "ready":
        submitted_diag_count = db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.student_id == student_id,
                Assessment.course_id == course_id,
                Assessment.kind == "diagnostic",
                Assessment.status.in_(["submitted", "completed"]),
            )
        ) or 0
        return StudentCourseState(
            student_id=student.id,
            course_id=course.id,
            student_name=student.name,
            course_name=course.name,
            kb_ready=False,
            needs_diagnostic=(submitted_diag_count == 0),
            topics=[],
            average_mastery=None,
            readiness=0.0,
            coverage_practiced=0,
            coverage_total=0,
            counts={"new": 0, "weak": 0, "learning": 0, "strong": 0, "due_for_review": 0},
            total_attempts=0,
            total_correct=0,
            overall_accuracy=None,
        )

    topic_by_id = {t.id: t for t in all_topics}
    parent_ids = {t.parent_id for t in all_topics if t.parent_id is not None}
    leaf_topics = [t for t in all_topics if t.id not in parent_ids]
    leaf_ids = [t.id for t in leaf_topics]

    # Map each topic to its leaf descendants (for prerequisites that point to non-leaf topics)
    children_map: Dict[int, List[int]] = {}
    for t in all_topics:
        if t.parent_id is not None:
            children_map.setdefault(t.parent_id, []).append(t.id)

    def get_leaves_for_topic(tid: int) -> List[int]:
        children = children_map.get(tid, [])
        if not children:
            return [tid]
        res: List[int] = []
        for c in children:
            res.extend(get_leaves_for_topic(c))
        return res

    # 3. Fetch chunk counts per leaf topic in bulk
    chunk_counts_rows = db.execute(
        select(ChunkTopic.topic_id, func.count(ChunkTopic.chunk_id))
        .where(ChunkTopic.topic_id.in_(leaf_ids))
        .group_by(ChunkTopic.topic_id)
    ).all()
    chunk_count_map = {row[0]: row[1] for row in chunk_counts_rows}

    # 4. Fetch prerequisites in bulk
    prereqs_rows = db.execute(
        select(TopicPrereq.topic_id, TopicPrereq.prereq_topic_id)
        .where(TopicPrereq.course_id == course_id)
    ).all()
    prereqs_map: Dict[int, List[int]] = {}
    for tid, pid in prereqs_rows:
        prereqs_map.setdefault(tid, []).append(pid)

    # 5. Fetch student Mastery rows for leaf topics in bulk
    mastery_rows = db.scalars(
        select(Mastery).where(
            Mastery.student_id == student_id,
            Mastery.topic_id.in_(leaf_ids),
        )
    ).all()
    mastery_map = {m.topic_id: m for m in mastery_rows}

    # 6. Fetch MasteryEvents for leaf topics in bulk (last 8 per topic)
    events_rows = db.scalars(
        select(MasteryEvent)
        .where(
            MasteryEvent.student_id == student_id,
            MasteryEvent.topic_id.in_(leaf_ids),
        )
        .order_by(MasteryEvent.created_at.desc())
    ).all()
    events_map: Dict[int, List[MasteryEvent]] = {}
    for ev in events_rows:
        ev_list = events_map.setdefault(ev.topic_id, [])
        if len(ev_list) < 8:
            ev_list.append(ev)

    # 7. Check if student submitted a diagnostic assessment in this course
    submitted_diag_count = db.scalar(
        select(func.count(Assessment.id)).where(
            Assessment.student_id == student_id,
            Assessment.course_id == course_id,
            Assessment.kind == "diagnostic",
            Assessment.status.in_(["submitted", "completed"]),
        )
    ) or 0

    # First pass: calculate topic raw states and effective mastery
    raw_states: List[LeafTopicState] = []
    eff_by_leaf_id: Dict[int, float] = {}

    for t in leaf_topics:
        parent_name = topic_by_id[t.parent_id].name if t.parent_id and t.parent_id in topic_by_id else None
        chunk_cnt = chunk_count_map.get(t.id, 0)
        m_row = mastery_map.get(t.id)

        if m_row:
            p_stored = m_row.p_mastery
            attempts = m_row.attempts_count
            correct = m_row.correct_count
            last_practiced = m_row.last_practiced_at
        else:
            p_stored = 0.0
            attempts = 0
            correct = 0
            last_practiced = None

        eff = effective_mastery(p_stored, last_practiced, correct, now=now)
        eff_by_leaf_id[t.id] = eff

        if last_practiced is not None:
            lp_tz = last_practiced.replace(tzinfo=timezone.utc) if last_practiced.tzinfo is None else last_practiced
            days_since = max(0.0, (now - lp_tz).total_seconds() / 86400.0)
            retriev = retrievability(days_since, correct)
        else:
            retriev = 1.0

        due = is_due(retriev, attempts)
        st = status_for(eff, attempts)

        # Build trend
        ev_list = events_map.get(t.id, [])
        trend_vals = [round(e.p_after, 4) for e in reversed(ev_list)]
        delta = round(trend_vals[-1] - trend_vals[0], 4) if len(trend_vals) >= 2 else 0.0

        state_item = LeafTopicState(
            id=t.id,
            name=t.name,
            parent_id=t.parent_id,
            parent_name=parent_name,
            order_index=t.order_index,
            chunk_count=chunk_cnt,
            p_mastery=p_stored,
            effective_mastery=eff,
            retrievability=round(retriev, 4),
            status=st,
            due_for_review=due,
            last_practiced_at=last_practiced,
            attempts_count=attempts,
            correct_count=correct,
            prerequisite_ids=prereqs_map.get(t.id, []),
            prerequisites=[],
            trend=trend_vals,
            trend_delta=delta,
        )
        raw_states.append(state_item)

    # Second pass: resolve prerequisites and their satisfaction
    def get_effective_for_any_topic(tid: int) -> float:
        leaves = get_leaves_for_topic(tid)
        if not leaves:
            return 0.0
        return sum(eff_by_leaf_id.get(lid, 0.0) for lid in leaves) / len(leaves)

    for item in raw_states:
        prereq_states: List[TopicPrereqState] = []
        for pid in item.prerequisite_ids:
            ptopic = topic_by_id.get(pid)
            pname = ptopic.name if ptopic else f"Topic {pid}"
            peff = get_effective_for_any_topic(pid)
            sat = peff >= settings.prereq_ok_above
            prereq_states.append(TopicPrereqState(id=pid, name=pname, satisfied=sat))
        item.prerequisites = prereq_states

    # Aggregate metrics
    practiced_topics = [t for t in raw_states if t.attempts_count > 0]
    coverage_practiced = len(practiced_topics)
    coverage_total = len(raw_states)

    avg_mastery = (
        round(sum(t.effective_mastery for t in practiced_topics) / coverage_practiced, 4)
        if coverage_practiced > 0
        else None
    )

    readiness = (
        round(sum(t.effective_mastery if t.attempts_count > 0 else 0.0 for t in raw_states) / coverage_total, 4)
        if coverage_total > 0
        else 0.0
    )

    counts = {"new": 0, "weak": 0, "learning": 0, "strong": 0, "due_for_review": 0}
    for t in raw_states:
        counts[t.status] = counts.get(t.status, 0) + 1
        if t.due_for_review:
            counts["due_for_review"] += 1

    total_attempts = sum(t.attempts_count for t in raw_states)
    total_correct = sum(t.correct_count for t in raw_states)
    overall_accuracy = (
        round(total_correct / total_attempts, 4) if total_attempts > 0 else None
    )

    needs_diagnostic = (total_attempts == 0 and submitted_diag_count == 0)

    return StudentCourseState(
        student_id=student.id,
        course_id=course.id,
        student_name=student.name,
        course_name=course.name,
        kb_ready=True,
        needs_diagnostic=needs_diagnostic,
        topics=raw_states,
        average_mastery=avg_mastery,
        readiness=readiness,
        coverage_practiced=coverage_practiced,
        coverage_total=coverage_total,
        counts=counts,
        total_attempts=total_attempts,
        total_correct=total_correct,
        overall_accuracy=overall_accuracy,
    )
