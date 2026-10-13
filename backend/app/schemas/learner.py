"""Pydantic schemas for learner model, mastery, dashboard, recommendations, and study plan."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TopicRef(BaseModel):
    """Reference to a topic with parent context."""

    id: int
    name: str
    parent_id: Optional[int] = None
    parent_name: Optional[str] = None


class TopicPrereqOut(BaseModel):
    """Prerequisite status for a leaf topic."""

    id: int
    name: str
    satisfied: bool


class LeafTopicMasteryOut(BaseModel):
    """Detailed mastery state of a leaf topic."""

    topic: TopicRef
    p_mastery: float
    effective_mastery: float
    retrievability: float
    status: str
    attempts: int
    correct: int
    accuracy: Optional[float] = None
    last_practiced_at: Optional[datetime] = None
    due_for_review: bool
    trend: List[float] = []
    trend_delta: float = 0.0
    prerequisites: List[TopicPrereqOut] = []


class CoverageOut(BaseModel):
    """Practiced vs total topic coverage."""

    practiced: int
    total: int


class CountsOut(BaseModel):
    """Status counts across leaf topics."""

    new: int
    weak: int
    learning: int
    strong: int
    due_for_review: int


class CourseMasteryResponse(BaseModel):
    """Response payload for GET /students/{sid}/courses/{cid}/mastery."""

    student_id: int
    course_id: int
    average_mastery: Optional[float] = None
    readiness: float
    coverage: CoverageOut
    counts: CountsOut
    topics: List[LeafTopicMasteryOut]
    kb_not_ready: Optional[bool] = None


class MasteryHistoryEventOut(BaseModel):
    """Audit event for mastery history endpoint."""

    created_at: datetime
    origin: str
    p_before: float
    p_after: float
    attempt_id: Optional[int] = None


class TopicMasteryHistoryResponse(BaseModel):
    """Response payload for GET /students/{sid}/courses/{cid}/topics/{tid}/mastery-history."""

    topic: TopicRef
    events: List[MasteryHistoryEventOut]


class RecommendationCTAOut(BaseModel):
    """Action button details for recommendation."""

    kind: str
    topic_ids: List[int] = []
    suggested_question_count: Optional[int] = None


class RecommendationOut(BaseModel):
    """Individual learner recommendation."""

    type: str
    priority: int
    topic: Optional[TopicRef] = None
    reason: str
    mastery: Optional[float] = None
    status: Optional[str] = None
    cta: RecommendationCTAOut
    citations: List[Dict[str, Any]] = []


class StudentRef(BaseModel):
    """Student reference for dashboard."""

    id: int
    name: str


class CourseRef(BaseModel):
    """Course reference for dashboard."""

    id: int
    name: str


class DashboardSummaryOut(BaseModel):
    """Summary metrics displayed on the learner dashboard."""

    average_mastery: Optional[float] = None
    readiness: float
    coverage: CoverageOut
    counts: CountsOut
    total_attempts: int
    overall_accuracy: Optional[float] = None
    questions_last_7_days: int
    study_days_last_7: int


class TopicLevelOut(BaseModel):
    """Topic with effective mastery and status."""

    topic: TopicRef
    effective_mastery: float
    status: str


class RecentAttemptOut(BaseModel):
    """Recent question attempt representation."""

    question_id: int
    topic: TopicRef
    qtype: str
    difficulty: str
    is_correct: bool
    score: float
    created_at: datetime


class RecentAssessmentOut(BaseModel):
    """Recent submitted assessment."""

    id: int
    kind: str
    title: str
    score: Optional[float] = None
    submitted_at: Optional[datetime] = None


class RecentPerformanceOut(BaseModel):
    """Recent attempts and assessments."""

    last_attempts: List[RecentAttemptOut] = []
    last_assessments: List[RecentAssessmentOut] = []
    accuracy_trend: List[float] = []


class DailyActivityOut(BaseModel):
    """Activity counts for a single day."""

    date: str
    attempts: int
    correct: int


class ActivityOut(BaseModel):
    """Streak and 14-day activity heatmap."""

    streak_days: int
    last_active_at: Optional[datetime] = None
    daily: List[DailyActivityOut] = []


class DashboardResponse(BaseModel):
    """Comprehensive learner dashboard payload."""

    student: StudentRef
    course: CourseRef
    needs_diagnostic: bool
    summary: DashboardSummaryOut
    strong_topics: List[TopicLevelOut] = []
    weak_topics: List[TopicLevelOut] = []
    due_for_review: List[TopicLevelOut] = []
    recent_performance: RecentPerformanceOut
    activity: ActivityOut
    next_action: Optional[RecommendationOut] = None
    recommendations: List[RecommendationOut] = []
    kb_not_ready: Optional[bool] = None


class ActivityHistoryItem(BaseModel):
    """Combined activity history item (attempt or assessment)."""

    type: str  # "attempt" | "assessment"
    question_id: Optional[int] = None
    assessment_id: Optional[int] = None
    topic: Optional[TopicRef] = None
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    created_at: Optional[datetime] = None
    id: Optional[int] = None
    kind: Optional[str] = None
    title: Optional[str] = None
    answered_count: Optional[int] = None
    submitted_at: Optional[datetime] = None


class StudyPlanSessionOut(BaseModel):
    """Session block within study plan day."""

    topic: Optional[TopicRef] = None
    activity: str
    minutes: int
    reason: str
    cta: RecommendationCTAOut


class StudyPlanDayOut(BaseModel):
    """Daily schedule within study plan."""

    date: str
    total_minutes: int
    sessions: List[StudyPlanSessionOut]


class StudyPlanSummaryOut(BaseModel):
    """Summary of study plan."""

    days: int
    total_sessions: int
    topics_covered: List[Dict[str, Any]]
    weakest_topics: List[Dict[str, Any]]


class StudyPlanResponseOut(BaseModel):
    """Response payload for GET /students/{sid}/courses/{cid}/study-plan."""

    days: List[StudyPlanDayOut]
    summary: StudyPlanSummaryOut


class DevAgeMasteryRequest(BaseModel):
    """Request payload to shift student mastery last_practiced_at back in time."""

    student_id: int
    course_id: int
    days: float = Field(gt=0.0)


class DevAgeMasteryResponse(BaseModel):
    """Response payload for /dev/age-mastery."""

    rows_affected: int


class DevForgettingSimulateRequest(BaseModel):
    """Request payload for /dev/forgetting-simulate."""

    p_mastery: float
    correct_count: int
    days: List[float]


class DevForgettingSimulateItem(BaseModel):
    """Single point in simulated forgetting trajectory."""

    days: float
    retrievability: float
    effective_mastery: float
