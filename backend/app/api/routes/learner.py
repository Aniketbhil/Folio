"""Learner endpoints: course mastery, dashboard, recommendations, history, and study plan."""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.assessment import Assessment, Attempt, Question
from app.models.conversation import Conversation, Message
from app.models.course import Course
from app.models.mastery import MasteryEvent
from app.models.source import Chunk
from app.models.student import Student
from app.models.topic import ChunkTopic, Topic
from app.schemas.citation import Citation
from app.services.auth.dependencies import get_current_student, require_same_student
from app.schemas.learner import (
    ActivityHistoryItem,
    ActivityOut,
    CountsOut,
    CourseMasteryResponse,
    CourseRef,
    CoverageOut,
    DailyActivityOut,
    DashboardResponse,
    DashboardSummaryOut,
    LeafTopicMasteryOut,
    RecentAssessmentOut,
    RecentAttemptOut,
    RecentPerformanceOut,
    RecommendationCTAOut,
    RecommendationOut,
    StudentRef,
    StudyPlanDayOut,
    StudyPlanResponseOut,
    StudyPlanSessionOut,
    StudyPlanSummaryOut,
    TopicLevelOut,
    TopicMasteryHistoryResponse,
    TopicPrereqOut,
    TopicRef,
)
from app.services.citations import build_citation
from app.services.learner.planner import build_study_plan
from app.services.learner.profile import load_student_course_state
from app.services.learner.recommendations import generate_recommendations

logger = logging.getLogger(__name__)

router = APIRouter(tags=["learner"])


def _build_citations_map_for_topics(
    db: Session,
    topic_ids: List[int],
) -> Dict[int, List[Dict[str, Any]]]:
    """Pre-load top citations for topics in bulk to avoid per-topic queries."""
    if not topic_ids:
        return {}

    # Bulk fetch top chunk associations
    rows = db.execute(
        select(ChunkTopic.topic_id, ChunkTopic.chunk_id, ChunkTopic.relevance)
        .where(ChunkTopic.topic_id.in_(topic_ids))
        .order_by(ChunkTopic.topic_id.asc(), ChunkTopic.relevance.desc())
    ).all()

    chunk_ids = list({r[1] for r in rows})
    if not chunk_ids:
        return {}

    # Bulk fetch chunks and sources
    chunks = db.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()
    chunk_map = {c.id: c for c in chunks}

    citations_by_topic: Dict[int, List[Dict[str, Any]]] = {}
    for tid, cid, _ in rows:
        c_list = citations_by_topic.setdefault(tid, [])
        if len(c_list) >= 2:
            continue
        chk = chunk_map.get(cid)
        if chk and chk.source:
            cit = build_citation(chk, chk.source)
            c_list.append(cit.model_dump())

    return citations_by_topic


@router.get(
    "/students/{student_id}/courses/{course_id}/mastery",
    response_model=CourseMasteryResponse,
)
def get_course_mastery(
    student_id: int,
    course_id: int,
    tz_offset_min: int = Query(default=0, ge=-840, le=840),
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> CourseMasteryResponse:
    """Retrieve full course topic breakdown with effective decayed mastery and trends."""
    require_same_student(current_student, student_id)

    state = load_student_course_state(
        db=db,
        student_id=student_id,
        course_id=course_id,
        tz_offset_min=tz_offset_min,
    )

    if not state.kb_ready:
        return CourseMasteryResponse(
            student_id=student_id,
            course_id=course_id,
            average_mastery=None,
            readiness=0.0,
            coverage=CoverageOut(practiced=0, total=0),
            counts=CountsOut(new=0, weak=0, learning=0, strong=0, due_for_review=0),
            topics=[],
            kb_not_ready=True,
        )

    topics_out: List[LeafTopicMasteryOut] = []
    for t in state.topics:
        acc = round(t.correct_count / t.attempts_count, 4) if t.attempts_count > 0 else None
        topics_out.append(
            LeafTopicMasteryOut(
                topic=TopicRef(
                    id=t.id,
                    name=t.name,
                    parent_id=t.parent_id,
                    parent_name=t.parent_name,
                ),
                p_mastery=t.p_mastery,
                effective_mastery=t.effective_mastery,
                retrievability=t.retrievability,
                status=t.status,
                attempts=t.attempts_count,
                correct=t.correct_count,
                accuracy=acc,
                last_practiced_at=t.last_practiced_at,
                due_for_review=t.due_for_review,
                trend=t.trend,
                trend_delta=t.trend_delta,
                prerequisites=[
                    TopicPrereqOut(id=pr.id, name=pr.name, satisfied=pr.satisfied)
                    for pr in t.prerequisites
                ],
            )
        )

    return CourseMasteryResponse(
        student_id=student_id,
        course_id=course_id,
        average_mastery=state.average_mastery,
        readiness=state.readiness,
        coverage=CoverageOut(
            practiced=state.coverage_practiced,
            total=state.coverage_total,
        ),
        counts=CountsOut(**state.counts),
        topics=topics_out,
        kb_not_ready=False,
    )


@router.get(
    "/students/{student_id}/courses/{course_id}/topics/{topic_id}/mastery-history",
    response_model=TopicMasteryHistoryResponse,
)
def get_topic_mastery_history(
    student_id: int,
    course_id: int,
    topic_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> TopicMasteryHistoryResponse:
    """Retrieve chronological mastery change history for a single leaf topic."""
    require_same_student(current_student, student_id)

    student = db.get(Student, student_id)
    if not student:
        raise AppError(f"Student {student_id} not found", code="student_not_found", status_code=404)

    course = db.get(Course, course_id)
    if not course:
        raise AppError(f"Course {course_id} not found", code="course_not_found", status_code=404)

    topic = db.get(Topic, topic_id)
    if not topic or topic.course_id != course_id:
        raise AppError(f"Topic {topic_id} not found in course {course_id}", code="topic_not_found", status_code=404)

    # Confirm topic is a leaf topic
    has_sub = db.scalar(select(func.count(Topic.id)).where(Topic.parent_id == topic_id)) or 0
    if has_sub > 0:
        raise AppError(f"Topic {topic_id} is not a leaf topic", code="topic_not_found", status_code=404)

    events = db.scalars(
        select(MasteryEvent)
        .where(
            MasteryEvent.student_id == student_id,
            MasteryEvent.topic_id == topic_id,
        )
        .order_by(MasteryEvent.created_at.asc(), MasteryEvent.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()

    return TopicMasteryHistoryResponse(
        topic=TopicRef(id=topic.id, name=topic.name, parent_id=topic.parent_id),
        events=[
            {
                "created_at": ev.created_at,
                "origin": ev.origin,
                "p_before": ev.p_before,
                "p_after": ev.p_after,
                "attempt_id": ev.attempt_id,
            }
            for ev in events
        ],
    )


@router.get(
    "/students/{student_id}/courses/{course_id}/dashboard",
    response_model=DashboardResponse,
)
def get_learner_dashboard(
    student_id: int,
    course_id: int,
    tz_offset_min: int = Query(default=0, ge=-840, le=840),
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    """Retrieve comprehensive learner dashboard with weak/strong topics, activity, and next action."""
    require_same_student(current_student, student_id)

    settings = get_settings()

    state = load_student_course_state(
        db=db,
        student_id=student_id,
        course_id=course_id,
        tz_offset_min=tz_offset_min,
    )

    if not state.kb_ready:
        next_act: Optional[RecommendationOut] = None
        recs_out: List[RecommendationOut] = []
        if state.needs_diagnostic:
            next_act = RecommendationOut(
                type="take_diagnostic",
                priority=1,
                topic=None,
                reason="Take the diagnostic assessment to establish your baseline knowledge across all course topics.",
                mastery=None,
                status=None,
                cta=RecommendationCTAOut(
                    kind="diagnostic",
                    topic_ids=[],
                    suggested_question_count=settings.diagnostic_questions,
                ),
                citations=[],
            )
            recs_out = [next_act]

        return DashboardResponse(
            student=StudentRef(id=state.student_id, name=state.student_name),
            course=CourseRef(id=state.course_id, name=state.course_name),
            needs_diagnostic=state.needs_diagnostic,
            summary=DashboardSummaryOut(
                average_mastery=None,
                readiness=0.0,
                coverage=CoverageOut(practiced=0, total=0),
                counts=CountsOut(new=0, weak=0, learning=0, strong=0, due_for_review=0),
                total_attempts=0,
                overall_accuracy=None,
                questions_last_7_days=0,
                study_days_last_7=0,
            ),
            strong_topics=[],
            weak_topics=[],
            due_for_review=[],
            recent_performance=RecentPerformanceOut(
                last_attempts=[],
                last_assessments=[],
                accuracy_trend=[],
            ),
            activity=ActivityOut(streak_days=0, last_active_at=None, daily=[]),
            next_action=next_act,
            recommendations=recs_out,
            kb_not_ready=True,
        )

    # 1. Weak / Strong / Due topics lists
    practiced_weak = [
        t for t in state.topics
        if t.attempts_count > 0 and t.status == "weak"
    ]
    practiced_weak.sort(key=lambda t: (t.effective_mastery, t.order_index, t.id))
    weak_topics_out = [
        TopicLevelOut(
            topic=TopicRef(id=t.id, name=t.name, parent_name=t.parent_name),
            effective_mastery=t.effective_mastery,
            status=t.status,
        )
        for t in practiced_weak[:5]
    ]

    practiced_strong = [t for t in state.topics if t.status == "strong"]
    practiced_strong.sort(key=lambda t: (-t.effective_mastery, t.order_index, t.id))
    strong_topics_out = [
        TopicLevelOut(
            topic=TopicRef(id=t.id, name=t.name, parent_name=t.parent_name),
            effective_mastery=t.effective_mastery,
            status=t.status,
        )
        for t in practiced_strong[:5]
    ]

    due_list = [t for t in state.topics if t.due_for_review]
    due_list.sort(key=lambda t: (t.retrievability, t.order_index, t.id))
    due_for_review_out = [
        TopicLevelOut(
            topic=TopicRef(id=t.id, name=t.name, parent_name=t.parent_name),
            effective_mastery=t.effective_mastery,
            status=t.status,
        )
        for t in due_list[:5]
    ]

    # 2. Recent attempts & assessments
    recent_attempts_rows = db.execute(
        select(Attempt, Question, Topic)
        .join(Question, Question.id == Attempt.question_id)
        .join(Topic, Topic.id == Question.topic_id)
        .where(Attempt.student_id == student_id, Question.course_id == course_id)
        .order_by(Attempt.created_at.desc(), Attempt.id.desc())
        .limit(settings.dash_recent_attempts)
    ).all()

    last_attempts_out = [
        RecentAttemptOut(
            question_id=att.question_id,
            topic=TopicRef(id=top.id, name=top.name),
            qtype=q.qtype,
            difficulty=q.difficulty,
            is_correct=att.is_correct,
            score=att.score,
            created_at=att.created_at,
        )
        for att, q, top in recent_attempts_rows
    ]

    last_assessments_rows = list(
        db.scalars(
            select(Assessment)
            .where(
                Assessment.student_id == student_id,
                Assessment.course_id == course_id,
                Assessment.status.in_(["submitted", "completed"]),
            )
            .order_by(Assessment.submitted_at.desc(), Assessment.id.desc())
            .limit(5)
        ).all()
    )

    last_assessments_out = [
        RecentAssessmentOut(
            id=a.id,
            kind=a.kind,
            title=a.title,
            score=a.score,
            submitted_at=a.submitted_at,
        )
        for a in last_assessments_rows
    ]

    accuracy_trend = [
        round(a.score, 4)
        for a in reversed(last_assessments_rows)
        if a.score is not None
    ]

    # 3. Activity streak, heatmap & 7-day stats
    now_utc = datetime.now(timezone.utc)
    offset_delta = timedelta(minutes=tz_offset_min)
    today_local = (now_utc + offset_delta).date()

    # Bulk fetch attempt timestamps and chat timestamps
    attempt_times = db.execute(
        select(Attempt.created_at, Attempt.is_correct)
        .join(Question, Question.id == Attempt.question_id)
        .where(Attempt.student_id == student_id, Question.course_id == course_id)
    ).all()

    chat_times = db.scalars(
        select(Message.created_at)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.student_id == student_id,
            Conversation.course_id == course_id,
            Message.role == "user",
        )
    ).all()

    dates_14 = [today_local - timedelta(days=i) for i in reversed(range(14))]
    daily_map: Dict[date, Dict[str, int]] = {
        d: {"attempts": 0, "correct": 0} for d in dates_14
    }
    active_days: set[date] = set()
    latest_active_ts: Optional[datetime] = None

    for dt, is_corr in attempt_times:
        dt_tz = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        if latest_active_ts is None or dt_tz > latest_active_ts:
            latest_active_ts = dt_tz
        local_d = (dt_tz + offset_delta).date()
        active_days.add(local_d)
        if local_d in daily_map:
            daily_map[local_d]["attempts"] += 1
            if is_corr:
                daily_map[local_d]["correct"] += 1

    for dt in chat_times:
        dt_tz = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        if latest_active_ts is None or dt_tz > latest_active_ts:
            latest_active_ts = dt_tz
        local_d = (dt_tz + offset_delta).date()
        active_days.add(local_d)

    # Consecutive streak ending today or yesterday
    streak = 0
    check_d = today_local
    if check_d not in active_days:
        check_d = today_local - timedelta(days=1)

    while check_d in active_days:
        streak += 1
        check_d -= timedelta(days=1)

    daily_out = [
        DailyActivityOut(
            date=d.isoformat(),
            attempts=daily_map[d]["attempts"],
            correct=daily_map[d]["correct"],
        )
        for d in dates_14
    ]

    last_7_start = today_local - timedelta(days=6)
    questions_last_7 = sum(
        v["attempts"] for d, v in daily_map.items() if d >= last_7_start
    )
    study_days_last_7 = len(
        [d for d in active_days if d >= last_7_start]
    )

    # 4. Struggling signal from tutor questions
    seven_days_ago = now_utc - timedelta(days=7)
    asst_metas = db.scalars(
        select(Message.meta)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.student_id == student_id,
            Conversation.course_id == course_id,
            Message.role == "assistant",
            Message.created_at >= seven_days_ago,
        )
    ).all()

    struggle_counts: Dict[int, int] = {}
    for meta in asst_metas:
        if isinstance(meta, dict):
            for t in meta.get("related_topics", []):
                if isinstance(t, dict) and "id" in t:
                    struggle_counts[t["id"]] = struggle_counts.get(t["id"], 0) + 1

    struggle_topic_ids = [
        tid
        for tid, cnt in struggle_counts.items()
        if cnt >= settings.chat_struggle_asks
    ]

    # 5. Pre-load citations and compute recommendations
    leaf_ids = [t.id for t in state.topics]
    citations_map = _build_citations_map_for_topics(db, leaf_ids)

    recs = generate_recommendations(
        state=state,
        struggle_topic_ids=struggle_topic_ids,
        citations_map=citations_map,
        limit=3,
    )

    def _format_rec(r: Any) -> RecommendationOut:
        return RecommendationOut(
            type=r.type,
            priority=r.priority,
            topic=TopicRef(id=r.topic.id, name=r.topic.name, parent_name=r.topic.parent_name) if r.topic else None,
            reason=r.reason,
            mastery=r.mastery,
            status=r.status,
            cta=RecommendationCTAOut(
                kind=r.cta.kind,
                topic_ids=r.cta.topic_ids,
                suggested_question_count=r.cta.suggested_question_count,
            ),
            citations=r.citations,
        )

    recs_out = [_format_rec(r) for r in recs]
    next_action_out = recs_out[0] if recs_out else None

    return DashboardResponse(
        student=StudentRef(id=state.student_id, name=state.student_name),
        course=CourseRef(id=state.course_id, name=state.course_name),
        needs_diagnostic=state.needs_diagnostic,
        summary=DashboardSummaryOut(
            average_mastery=state.average_mastery,
            readiness=state.readiness,
            coverage=CoverageOut(
                practiced=state.coverage_practiced,
                total=state.coverage_total,
            ),
            counts=CountsOut(**state.counts),
            total_attempts=state.total_attempts,
            overall_accuracy=state.overall_accuracy,
            questions_last_7_days=questions_last_7,
            study_days_last_7=study_days_last_7,
        ),
        strong_topics=strong_topics_out,
        weak_topics=weak_topics_out,
        due_for_review=due_for_review_out,
        recent_performance=RecentPerformanceOut(
            last_attempts=last_attempts_out,
            last_assessments=last_assessments_out,
            accuracy_trend=accuracy_trend,
        ),
        activity=ActivityOut(
            streak_days=streak,
            last_active_at=latest_active_ts,
            daily=daily_out,
        ),
        next_action=next_action_out,
        recommendations=recs_out,
        kb_not_ready=False,
    )


@router.get(
    "/students/{student_id}/courses/{course_id}/recommendations",
    response_model=List[RecommendationOut],
)
def get_recommendations(
    student_id: int,
    course_id: int,
    limit: int = Query(default=5, ge=1, le=5),
    tz_offset_min: int = Query(default=0, ge=-840, le=840),
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> List[RecommendationOut]:
    """Retrieve prioritized next study actions with grounded citations."""
    require_same_student(current_student, student_id)

    settings = get_settings()

    state = load_student_course_state(
        db=db,
        student_id=student_id,
        course_id=course_id,
        tz_offset_min=tz_offset_min,
    )

    if not state.kb_ready:
        return []

    # Struggling topics count
    now_utc = datetime.now(timezone.utc)
    seven_days_ago = now_utc - timedelta(days=7)
    asst_metas = db.scalars(
        select(Message.meta)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.student_id == student_id,
            Conversation.course_id == course_id,
            Message.role == "assistant",
            Message.created_at >= seven_days_ago,
        )
    ).all()

    struggle_counts: Dict[int, int] = {}
    for meta in asst_metas:
        if isinstance(meta, dict):
            for t in meta.get("related_topics", []):
                if isinstance(t, dict) and "id" in t:
                    struggle_counts[t["id"]] = struggle_counts.get(t["id"], 0) + 1

    struggle_topic_ids = [
        tid
        for tid, cnt in struggle_counts.items()
        if cnt >= settings.chat_struggle_asks
    ]

    leaf_ids = [t.id for t in state.topics]
    citations_map = _build_citations_map_for_topics(db, leaf_ids)

    recs = generate_recommendations(
        state=state,
        struggle_topic_ids=struggle_topic_ids,
        citations_map=citations_map,
        limit=limit,
    )

    return [
        RecommendationOut(
            type=r.type,
            priority=r.priority,
            topic=TopicRef(id=r.topic.id, name=r.topic.name, parent_name=r.topic.parent_name) if r.topic else None,
            reason=r.reason,
            mastery=r.mastery,
            status=r.status,
            cta=RecommendationCTAOut(
                kind=r.cta.kind,
                topic_ids=r.cta.topic_ids,
                suggested_question_count=r.cta.suggested_question_count,
            ),
            citations=r.citations,
        )
        for r in recs
    ]


@router.get(
    "/students/{student_id}/courses/{course_id}/history",
    response_model=List[ActivityHistoryItem],
)
def get_activity_history(
    student_id: int,
    course_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    kind: str = Query(default="all", pattern="^(attempts|assessments|all)$"),
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> List[ActivityHistoryItem]:
    """Retrieve combined chronological activity stream of attempts and assessments."""
    require_same_student(current_student, student_id)

    student = db.get(Student, student_id)
    if not student:
        raise AppError(f"Student {student_id} not found", code="student_not_found", status_code=404)

    course = db.get(Course, course_id)
    if not course:
        raise AppError(f"Course {course_id} not found", code="course_not_found", status_code=404)

    items: List[ActivityHistoryItem] = []

    if kind in ("attempts", "all"):
        attempt_rows = db.execute(
            select(Attempt, Question, Topic)
            .join(Question, Question.id == Attempt.question_id)
            .join(Topic, Topic.id == Question.topic_id)
            .where(Attempt.student_id == student_id, Question.course_id == course_id)
            .order_by(Attempt.created_at.desc(), Attempt.id.desc())
            .limit(limit + offset)
        ).all()

        for att, q, top in attempt_rows:
            items.append(
                ActivityHistoryItem(
                    type="attempt",
                    question_id=att.question_id,
                    assessment_id=q.assessment_id,
                    topic=TopicRef(id=top.id, name=top.name),
                    is_correct=att.is_correct,
                    score=att.score,
                    created_at=att.created_at,
                )
            )

    if kind in ("assessments", "all"):
        assessments_rows = db.scalars(
            select(Assessment)
            .where(
                Assessment.student_id == student_id,
                Assessment.course_id == course_id,
                Assessment.status.in_(["submitted", "completed"]),
            )
            .order_by(Assessment.submitted_at.desc(), Assessment.id.desc())
            .limit(limit + offset)
        ).all()

        for a in assessments_rows:
            # Count answered questions
            answered = db.scalar(
                select(func.count(Attempt.id)).where(Attempt.assessment_id == a.id)
            ) or 0
            items.append(
                ActivityHistoryItem(
                    type="assessment",
                    id=a.id,
                    kind=a.kind,
                    title=a.title,
                    score=a.score,
                    answered_count=answered,
                    submitted_at=a.submitted_at,
                )
            )

    # Sort merged list newest first
    def _sort_key(item: ActivityHistoryItem) -> datetime:
        dt = item.created_at or item.submitted_at
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    items.sort(key=_sort_key, reverse=True)
    return items[offset : offset + limit]


@router.get(
    "/students/{student_id}/courses/{course_id}/study-plan",
    response_model=StudyPlanResponseOut,
)
def get_study_plan(
    student_id: int,
    course_id: int,
    exam_date: Optional[str] = Query(default=None),
    minutes_per_day: int = Query(default=45, ge=15, le=480),
    tz_offset_min: int = Query(default=0, ge=-840, le=840),
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> StudyPlanResponseOut:
    """Generate a calendarized study plan based on exam horizon and student mastery need."""
    require_same_student(current_student, student_id)

    student = db.get(Student, student_id)
    if not student:
        raise AppError(f"Student {student_id} not found", code="student_not_found", status_code=404)

    course = db.get(Course, course_id)
    if not course:
        raise AppError(f"Course {course_id} not found", code="course_not_found", status_code=404)

    parsed_exam_date: Optional[date] = None
    if exam_date:
        try:
            parsed_exam_date = date.fromisoformat(exam_date.strip())
        except ValueError:
            raise AppError(
                "exam_date must be in YYYY-MM-DD format",
                code="invalid_exam_date",
                status_code=422,
            )

    state = load_student_course_state(
        db=db,
        student_id=student_id,
        course_id=course_id,
        tz_offset_min=tz_offset_min,
    )

    now_utc = datetime.now(timezone.utc)
    today_local = (now_utc + timedelta(minutes=tz_offset_min)).date()

    plan_result = build_study_plan(
        state=state,
        today=today_local,
        exam_date=parsed_exam_date,
        minutes_per_day=minutes_per_day,
    )

    # Format response
    days_out: List[StudyPlanDayOut] = []
    for d in plan_result.days:
        sessions_out: List[StudyPlanSessionOut] = []
        for s in d.sessions:
            sessions_out.append(
                StudyPlanSessionOut(
                    topic=TopicRef(id=s.topic.id, name=s.topic.name) if s.topic else None,
                    activity=s.activity,
                    minutes=s.minutes,
                    reason=s.reason,
                    cta=RecommendationCTAOut(
                        kind=s.cta.kind,
                        topic_ids=s.cta.topic_ids,
                    ),
                )
            )
        days_out.append(
            StudyPlanDayOut(
                date=d.date,
                total_minutes=d.total_minutes,
                sessions=sessions_out,
            )
        )

    return StudyPlanResponseOut(
        days=days_out,
        summary=StudyPlanSummaryOut(
            days=plan_result.summary.days,
            total_sessions=plan_result.summary.total_sessions,
            topics_covered=plan_result.summary.topics_covered,
            weakest_topics=plan_result.summary.weakest_topics,
        ),
    )
