"""Deterministic study planner for student course mastery.

Pure functions with zero database access. Builds a calendarized study plan:
- Horizon: up to 60 days if exam_date provided; otherwise next 7 days.
- Block-based daily scheduling based on study_session_min and minutes_per_day.
- Need scoring prioritizing weak topics, large chunk topics, and due reviews.
- Prerequisite resolution scheduling root-cause prerequisite topics first.
- Spaced repetition review blocks scheduled on d+2 and d+5.
- Mock exam and weakest-topic reviews scheduled before exam day.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.learner.profile import LeafTopicState, StudentCourseState


@dataclass
class StudyPlanTopic:
    """Topic reference in study session."""

    id: int
    name: str


@dataclass
class StudyPlanCTA:
    """Action button details for a study session."""

    kind: str  # "tutor" | "quiz" | "mock_exam" | "source"
    topic_ids: List[int] = field(default_factory=list)


@dataclass
class StudySession:
    """Individual study session block."""

    topic: Optional[StudyPlanTopic]
    activity: str  # "learn" | "practice" | "review" | "mock_exam"
    minutes: int
    reason: str
    cta: StudyPlanCTA


@dataclass
class StudyDay:
    """Day schedule in the study plan."""

    date: str
    total_minutes: int
    sessions: List[StudySession]


@dataclass
class StudyPlanSummary:
    """Summary metrics of the generated study plan."""

    days: int
    total_sessions: int
    topics_covered: List[Dict[str, Any]]
    weakest_topics: List[Dict[str, Any]]


@dataclass
class StudyPlanResponse:
    """Complete response object for the study plan."""

    days: List[StudyDay]
    summary: StudyPlanSummary


def build_study_plan(
    state: StudentCourseState,
    today: date,
    exam_date: Optional[date],
    minutes_per_day: int,
) -> StudyPlanResponse:
    """Generate a deterministic, rule-based study plan.

    Args:
        state: Loaded StudentCourseState
        today: Current date
        exam_date: Optional target exam date
        minutes_per_day: Daily study budget in minutes (15..480)

    Returns:
        StudyPlanResponse with daily sessions and overall summary.
    """
    settings = get_settings()

    if minutes_per_day < 15 or minutes_per_day > 480:
        raise AppError(
            "minutes_per_day must be between 15 and 480",
            code="invalid_minutes",
            status_code=422,
        )

    # 1. Horizon calculation
    if exam_date is not None:
        if exam_date < today:
            raise AppError(
                "Exam date cannot be in the past",
                code="invalid_exam_date",
                status_code=422,
            )
        days_diff = (exam_date - today).days
        num_days = min(60, days_diff + 1)
    else:
        num_days = 7

    blocks_per_day = max(1, minutes_per_day // settings.study_session_min)

    if not state.topics:
        # Empty syllabus fallback
        empty_days = [
            StudyDay(
                date=(today + timedelta(days=d)).isoformat(),
                total_minutes=0,
                sessions=[],
            )
            for d in range(num_days)
        ]
        return StudyPlanResponse(
            days=empty_days,
            summary=StudyPlanSummary(
                days=num_days,
                total_sessions=0,
                topics_covered=[],
                weakest_topics=[],
            ),
        )

    # 2. Topic need score calculation
    topic_by_id: Dict[int, LeafTopicState] = {t.id: t for t in state.topics}
    max_chunk_cnt = max((t.chunk_count for t in state.topics), default=1) or 1

    remaining_need: Dict[int, float] = {}
    for t in state.topics:
        eff = settings.bkt_p_init if t.status == "new" else t.effective_mastery
        need = (1.0 - eff) * (1.0 + (t.chunk_count / max_chunk_cnt)) + (0.5 if t.due_for_review else 0.0)
        remaining_need[t.id] = need

    spaced_review_queue: Dict[int, List[int]] = {}
    plan_days: List[StudyDay] = []
    covered_topic_ids: Set[int] = set()

    # 3. Daily scheduling
    for d in range(num_days):
        day_date = today + timedelta(days=d)
        day_sessions: List[StudySession] = []

        is_exam_day = (exam_date is not None and d == num_days - 1)
        is_pre_exam_day = (exam_date is not None and num_days >= 2 and d == num_days - 2)

        if is_exam_day:
            # Mock exam on the final day
            mock_blocks = min(2, blocks_per_day)
            for _ in range(mock_blocks):
                day_sessions.append(
                    StudySession(
                        topic=None,
                        activity="mock_exam",
                        minutes=settings.study_session_min,
                        reason="Comprehensive mock exam covering all topics before exam day.",
                        cta=StudyPlanCTA(kind="mock_exam", topic_ids=[t.id for t in state.topics]),
                    )
                )

        elif is_pre_exam_day:
            # Day before exam: Review weakest topics
            practiced_weak = [
                t for t in state.topics
                if t.attempts_count > 0 or t.status in ("weak", "learning")
            ]
            practiced_weak.sort(key=lambda t: (t.effective_mastery, t.order_index))
            review_candidates = practiced_weak if practiced_weak else state.topics

            idx = 0
            while len(day_sessions) < blocks_per_day and idx < len(review_candidates):
                t = review_candidates[idx % len(review_candidates)]
                covered_topic_ids.add(t.id)
                day_sessions.append(
                    StudySession(
                        topic=StudyPlanTopic(id=t.id, name=t.name),
                        activity="review",
                        minutes=settings.study_session_min,
                        reason=f"Pre-exam review of focus topic {t.name}.",
                        cta=StudyPlanCTA(kind="quiz", topic_ids=[t.id]),
                    )
                )
                idx += 1

        # Fill normal slots or remaining capacity
        while len(day_sessions) < blocks_per_day:
            # Check spaced review queue first
            if spaced_review_queue.get(d):
                tid = spaced_review_queue[d].pop(0)
                st = topic_by_id.get(tid)
                if st:
                    covered_topic_ids.add(st.id)
                    day_sessions.append(
                        StudySession(
                            topic=StudyPlanTopic(id=st.id, name=st.name),
                            activity="review",
                            minutes=settings.study_session_min,
                            reason=f"Spaced review session for {st.name} to reinforce retention.",
                            cta=StudyPlanCTA(kind="quiz", topic_ids=[st.id]),
                        )
                    )
                    continue

            # Greedy pick highest remaining need topic
            candidates = sorted(
                state.topics,
                key=lambda t: (remaining_need.get(t.id, 0.0), -t.order_index),
                reverse=True,
            )
            chosen = candidates[0]

            # Prerequisite resolution: if chosen has an unsatisfied prerequisite that also needs work
            for pid in chosen.prerequisite_ids:
                pt = topic_by_id.get(pid)
                if pt and pt.effective_mastery < settings.prereq_ok_above and remaining_need.get(pt.id, 0.0) > 0.0:
                    chosen = pt
                    break

            covered_topic_ids.add(chosen.id)

            # Determine activity
            if chosen.status == "new":
                act = "learn"
                reason = f"Introductory study of core concepts in {chosen.name}."
                cta = StudyPlanCTA(kind="tutor", topic_ids=[chosen.id])
            elif chosen.status in ("weak", "learning"):
                act = "practice"
                reason = f"Targeted practice to strengthen mastery in {chosen.name}."
                cta = StudyPlanCTA(kind="quiz", topic_ids=[chosen.id])
            else:
                act = "review"
                reason = f"Refresher review to maintain strong retention in {chosen.name}."
                cta = StudyPlanCTA(kind="quiz", topic_ids=[chosen.id])

            day_sessions.append(
                StudySession(
                    topic=StudyPlanTopic(id=chosen.id, name=chosen.name),
                    activity=act,
                    minutes=settings.study_session_min,
                    reason=reason,
                    cta=cta,
                )
            )

            # If practice, register spaced reviews on d+2 and d+5
            if act == "practice":
                for offset in (2, 5):
                    target_d = d + offset
                    if target_d < num_days:
                        spaced_review_queue.setdefault(target_d, []).append(chosen.id)

            # Reduce remaining need by 0.35 to rotate topics
            remaining_need[chosen.id] = max(0.0, remaining_need.get(chosen.id, 0.0) - 0.35)

        total_min = len(day_sessions) * settings.study_session_min
        plan_days.append(
            StudyDay(
                date=day_date.isoformat(),
                total_minutes=total_min,
                sessions=day_sessions,
            )
        )

    # 4. Build summary
    covered_list = [
        {"id": t.id, "name": t.name}
        for t in state.topics
        if t.id in covered_topic_ids
    ]

    practiced_sorted = sorted(
        [t for t in state.topics if t.attempts_count > 0],
        key=lambda t: (t.effective_mastery, t.order_index),
    )
    weakest_list = [
        {"id": t.id, "name": t.name, "effective_mastery": t.effective_mastery}
        for t in practiced_sorted[:3]
    ]

    total_sessions_count = sum(len(d.sessions) for d in plan_days)

    summary = StudyPlanSummary(
        days=num_days,
        total_sessions=total_sessions_count,
        topics_covered=covered_list,
        weakest_topics=weakest_list,
    )

    return StudyPlanResponse(days=plan_days, summary=summary)
