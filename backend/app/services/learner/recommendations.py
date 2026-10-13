"""Deterministic rule-based recommendation engine for student study companion.

Pure functions with zero database access. Implements prioritized recommendations:
1. Diagnostic baseline if unpracticed
2. Weak topics / unsatisfied prerequisites (root cause first)
   - Struggling signal (frequent tutor inquiries)
3. Spaced review for decayed retrievability
4. New syllabus topics ready to learn in teaching order
5. Comprehensive mock exam if all topics strong
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.core.config import get_settings
from app.services.learner.profile import LeafTopicState, StudentCourseState


@dataclass
class RecommendationCTA:
    """Action button details for a recommendation."""

    kind: str  # "diagnostic" | "quiz" | "tutor" | "source" | "mock_exam"
    topic_ids: List[int] = field(default_factory=list)
    suggested_question_count: Optional[int] = None


@dataclass
class RecommendationTopic:
    """Topic reference in a recommendation."""

    id: int
    name: str
    parent_name: Optional[str] = None


@dataclass
class Recommendation:
    """Individual study recommendation."""

    type: str  # "take_diagnostic" | "practice_topic" | "review_topic" | "learn_topic" | "take_mock_exam" | "ask_tutor"
    priority: int
    topic: Optional[RecommendationTopic]
    reason: str
    mastery: Optional[float]
    status: Optional[str]
    cta: RecommendationCTA
    citations: List[Dict[str, Any]] = field(default_factory=list)


def generate_recommendations(
    state: StudentCourseState,
    struggle_topic_ids: Optional[List[int]] = None,
    citations_map: Optional[Dict[int, List[Dict[str, Any]]]] = None,
    limit: int = 5,
) -> List[Recommendation]:
    """Generate prioritized, deduplicated recommendations over student state.

    Args:
        state: Loaded StudentCourseState
        struggle_topic_ids: Topic IDs with frequent questions in recent tutor turns
        citations_map: Pre-loaded citations mapped by topic ID
        limit: Max items to return (1 to 5)

    Returns:
        List of Recommendation items sorted by priority (1-based).
    """
    settings = get_settings()
    if not state.kb_ready or not state.topics:
        return []

    citations_map = citations_map or {}
    items: List[Recommendation] = []
    seen_topic_ids: Set[int] = set()

    topic_by_id: Dict[int, LeafTopicState] = {t.id: t for t in state.topics}

    # 1. Diagnostic baseline if zero attempts and no submitted diagnostic
    if state.needs_diagnostic:
        items.append(
            Recommendation(
                type="take_diagnostic",
                priority=len(items) + 1,
                topic=None,
                reason="Take the diagnostic assessment to establish your baseline knowledge across all course topics.",
                mastery=None,
                status=None,
                cta=RecommendationCTA(
                    kind="diagnostic",
                    topic_ids=[],
                    suggested_question_count=settings.diagnostic_questions,
                ),
                citations=[],
            )
        )

    # 2. Weak topics ascending by effective mastery
    weak_topics = [
        t for t in state.topics
        if t.effective_mastery < settings.mastery_weak_below and t.attempts_count > 0
    ]
    weak_topics.sort(key=lambda t: (t.effective_mastery, t.order_index, t.id))

    for wt in weak_topics:
        # Check prerequisites of this weak topic
        unsatisfied_prereq: Optional[LeafTopicState] = None
        for pid in wt.prerequisite_ids:
            pt = topic_by_id.get(pid)
            if pt and pt.effective_mastery < settings.prereq_ok_above and (pt.attempts_count > 0 or pt.status == "weak"):
                unsatisfied_prereq = pt
                break

        if unsatisfied_prereq and unsatisfied_prereq.id not in seen_topic_ids:
            seen_topic_ids.add(unsatisfied_prereq.id)
            pct = int(round(unsatisfied_prereq.effective_mastery * 100))
            items.append(
                Recommendation(
                    type="practice_topic",
                    priority=len(items) + 1,
                    topic=RecommendationTopic(
                        id=unsatisfied_prereq.id,
                        name=unsatisfied_prereq.name,
                        parent_name=unsatisfied_prereq.parent_name,
                    ),
                    reason=f"Mastery in {unsatisfied_prereq.name} is {pct}%, which is a prerequisite for {wt.name}.",
                    mastery=unsatisfied_prereq.effective_mastery,
                    status=unsatisfied_prereq.status,
                    cta=RecommendationCTA(
                        kind="quiz",
                        topic_ids=[unsatisfied_prereq.id],
                        suggested_question_count=5,
                    ),
                    citations=citations_map.get(unsatisfied_prereq.id, [])[:2],
                )
            )
        elif wt.id not in seen_topic_ids:
            seen_topic_ids.add(wt.id)
            pct = int(round(wt.effective_mastery * 100))
            items.append(
                Recommendation(
                    type="practice_topic",
                    priority=len(items) + 1,
                    topic=RecommendationTopic(
                        id=wt.id,
                        name=wt.name,
                        parent_name=wt.parent_name,
                    ),
                    reason=f"Mastery in {wt.name} is {pct}%, below the proficiency threshold.",
                    mastery=wt.effective_mastery,
                    status=wt.status,
                    cta=RecommendationCTA(
                        kind="quiz",
                        topic_ids=[wt.id],
                        suggested_question_count=5,
                    ),
                    citations=citations_map.get(wt.id, [])[:2],
                )
            )

    # Struggling signal right after weak topics
    if struggle_topic_ids:
        for stid in struggle_topic_ids:
            st = topic_by_id.get(stid)
            if st and st.status != "strong" and st.id not in seen_topic_ids:
                seen_topic_ids.add(st.id)
                items.append(
                    Recommendation(
                        type="ask_tutor",
                        priority=len(items) + 1,
                        topic=RecommendationTopic(
                            id=st.id,
                            name=st.name,
                            parent_name=st.parent_name,
                        ),
                        reason="You've asked about this several times; try a focused quiz or review the source.",
                        mastery=st.effective_mastery,
                        status=st.status,
                        cta=RecommendationCTA(
                            kind="tutor",
                            topic_ids=[st.id],
                            suggested_question_count=None,
                        ),
                        citations=citations_map.get(st.id, [])[:2],
                    )
                )

    # 3. Due-for-review topics ordered by lowest retrievability
    due_topics = [t for t in state.topics if t.due_for_review]
    due_topics.sort(key=lambda t: (t.retrievability, t.order_index, t.id))

    for dt in due_topics:
        if dt.id not in seen_topic_ids:
            seen_topic_ids.add(dt.id)
            r_pct = int(round(dt.retrievability * 100))
            items.append(
                Recommendation(
                    type="review_topic",
                    priority=len(items) + 1,
                    topic=RecommendationTopic(
                        id=dt.id,
                        name=dt.name,
                        parent_name=dt.parent_name,
                    ),
                    reason=f"Memory retrievability has decayed to {r_pct}%; review to maintain retention.",
                    mastery=dt.effective_mastery,
                    status=dt.status,
                    cta=RecommendationCTA(
                        kind="quiz",
                        topic_ids=[dt.id],
                        suggested_question_count=5,
                    ),
                    citations=citations_map.get(dt.id, [])[:2],
                )
            )

    # 4. Never-practiced ("new") topics whose prerequisites are satisfied, in syllabus order
    new_topics = [
        t for t in state.topics
        if t.attempts_count == 0 and all(pr.satisfied for pr in t.prerequisites)
    ]
    new_topics.sort(key=lambda t: (t.order_index, t.id))

    for nt in new_topics:
        if nt.id not in seen_topic_ids:
            seen_topic_ids.add(nt.id)
            items.append(
                Recommendation(
                    type="learn_topic",
                    priority=len(items) + 1,
                    topic=RecommendationTopic(
                        id=nt.id,
                        name=nt.name,
                        parent_name=nt.parent_name,
                    ),
                    reason=f"New topic ready to learn in syllabus order: {nt.name}.",
                    mastery=nt.effective_mastery,
                    status=nt.status,
                    cta=RecommendationCTA(
                        kind="tutor",
                        topic_ids=[nt.id],
                        suggested_question_count=None,
                    ),
                    citations=citations_map.get(nt.id, [])[:2],
                )
            )

    # 5. Fallback: take mock exam if nothing else applies
    if not items:
        items.append(
            Recommendation(
                type="take_mock_exam",
                priority=1,
                topic=None,
                reason="All practiced topics are strong and retention is fresh. Take a comprehensive mock exam.",
                mastery=None,
                status=None,
                cta=RecommendationCTA(
                    kind="mock_exam",
                    topic_ids=[],
                    suggested_question_count=settings.exam_max_questions,
                ),
                citations=[],
            )
        )

    # Clamp to limit and re-index priorities
    limited = items[: max(1, min(5, limit))]
    for idx, rec in enumerate(limited, start=1):
        rec.priority = idx

    return limited
