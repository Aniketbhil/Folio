"""Topic selection, scope resolution, difficulty planning, and chunk allocation for assessments."""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.assessment import Question
from app.models.course import Course
from app.models.mastery import Mastery
from app.models.source import Chunk, Source
from app.models.student import Student
from app.models.topic import ChunkTopic, Concept, Topic
from app.services.citations import build_citation
from app.services.tutor.service import expand_topic_ids

logger = logging.getLogger(__name__)

NUMERICAL_INDICATORS = re.compile(
    r"\b(\d+(?:\.\d+)?|\bformula\b|\bequation\b|\bcalculate\b|\bvelocity\b|\bacceleration\b|\bmass\b|\bforce\b|\benergy\b|\bkg\b|\bm/s\b|\bN\b|\bJ\b|\bW\b)\b",
    re.IGNORECASE,
)


@dataclass
class TopicContext:
    """Prepared context and source material for a topic in an assessment."""

    topic: Topic
    parent_topic: Optional[Topic]
    concepts: List[Concept]
    chunks: List[Chunk]
    source_map: Dict[int, Source]
    chunk_citations: List[Dict]
    requested_count: int
    assigned_qtypes: List[str]
    assigned_difficulties: List[str]
    has_numerical_support: bool


def resolve_assessment_scope(
    db: Session,
    course_id: int,
    student_id: int,
    kind: str,
    raw_topic_ids: Optional[List[int]],
    num_questions: Optional[int],
    difficulty: str,
    question_types: Optional[List[str]],
) -> Tuple[List[Topic], int, List[str], List[str]]:
    """Validate input parameters, resolve topic scope, and prepare generation targets.

    Returns:
        (eligible_topics, target_num_questions, warnings, allowed_question_types)
    """
    settings = get_settings()
    warnings: List[str] = []

    # 1. Validate student and course
    student = db.get(Student, student_id)
    if not student:
        raise AppError(
            f"Student with id {student_id} not found",
            code="student_not_found",
            status_code=404,
        )

    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    # 2. Check knowledge base readiness
    if course.kb_built_at is None or course.kb_error is not None:
        raise AppError(
            "Knowledge base is not ready yet.",
            code="kb_not_ready",
            status_code=409,
        )

    # 3. Validate assessment kind
    valid_kinds = {"quiz", "mock_exam", "diagnostic"}
    if kind not in valid_kinds:
        raise AppError(
            f"Invalid assessment kind '{kind}'. Allowed kinds: {sorted(valid_kinds)}",
            code="validation_error",
            status_code=422,
        )

    # 4. Resolve topic IDs
    course_topic_ids = set(
        db.scalars(select(Topic.id).where(Topic.course_id == course_id)).all()
    )
    if not course_topic_ids:
        raise AppError(
            "Knowledge base is not ready yet.",
            code="kb_not_ready",
            status_code=409,
        )

    if raw_topic_ids is not None:
        for tid in raw_topic_ids:
            if tid not in course_topic_ids:
                raise AppError(
                    f"Topic with id {tid} not found in course {course_id}",
                    code="topic_not_found",
                    status_code=404,
                )
        expanded_ids = expand_topic_ids(db, course_id, raw_topic_ids)
    else:
        # All leaf topics in the course
        expanded_ids = expand_topic_ids(db, course_id, list(course_topic_ids))

    if not expanded_ids:
        raise AppError(
            "Knowledge base is not ready yet.",
            code="kb_not_ready",
            status_code=409,
        )

    # 5. Filter for eligible leaf topics that have at least 1 tagged embedded chunk
    leaf_topics_with_chunks = set(
        db.scalars(
            select(ChunkTopic.topic_id)
            .join(Chunk, Chunk.id == ChunkTopic.chunk_id)
            .where(
                ChunkTopic.topic_id.in_(expanded_ids),
                Chunk.course_id == course_id,
                Chunk.embedded == True,
            )
            .distinct()
        ).all()
    )

    eligible_topics = list(
        db.scalars(
            select(Topic)
            .where(Topic.id.in_(leaf_topics_with_chunks))
            .order_by(Topic.id.asc())
        ).all()
    )

    if not eligible_topics:
        raise AppError(
            "Knowledge base is not ready yet.",
            code="kb_not_ready",
            status_code=409,
        )

    # 6. Validate question count limits
    if kind == "quiz":
        target_num = num_questions if num_questions is not None else 5
        if target_num < 1 or target_num > settings.quiz_max_questions:
            raise AppError(
                f"num_questions for quiz must be between 1 and {settings.quiz_max_questions}",
                code="validation_error",
                status_code=422,
            )
    elif kind == "mock_exam":
        target_num = num_questions if num_questions is not None else 20
        if target_num < 1 or target_num > settings.exam_max_questions:
            raise AppError(
                f"num_questions for mock_exam must be between 1 and {settings.exam_max_questions}",
                code="validation_error",
                status_code=422,
            )
    elif kind == "diagnostic":
        # diagnostic ignores num_questions and targets min(DIAGNOSTIC_QUESTIONS, len(eligible_topics))
        target_num = min(settings.diagnostic_questions, len(eligible_topics))

    # 7. Validate difficulty
    valid_difficulties = {"auto", "easy", "medium", "hard"}
    if difficulty not in valid_difficulties:
        raise AppError(
            f"Invalid difficulty '{difficulty}'. Allowed: {sorted(valid_difficulties)}",
            code="validation_error",
            status_code=422,
        )

    # 8. Validate question types
    valid_qtypes = {"mcq", "short_answer", "numerical"}
    if kind == "diagnostic":
        qtypes = ["mcq"]
    else:
        if question_types is None:
            qtypes = ["mcq", "short_answer"]
        else:
            if not question_types:
                raise AppError(
                    "question_types cannot be empty",
                    code="validation_error",
                    status_code=422,
                )
            for qt in question_types:
                if qt not in valid_qtypes:
                    raise AppError(
                        f"Invalid question type '{qt}'. Allowed: {sorted(valid_qtypes)}",
                        code="validation_error",
                        status_code=422,
                    )
            qtypes = list(dict.fromkeys(question_types))  # deduplicate preserving order

    return eligible_topics, target_num, warnings, qtypes


def allocate_questions_across_topics(
    db: Session,
    student_id: int,
    topics: List[Topic],
    target_count: int,
    kind: str,
) -> Dict[int, int]:
    """Determine exactly how many questions each topic will receive."""
    if not topics or target_count <= 0:
        return {}

    # Fetch mastery records for the student across all candidate topics
    masteries = {
        m.topic_id: m
        for m in db.scalars(
            select(Mastery).where(
                Mastery.student_id == student_id,
                Mastery.topic_id.in_([t.id for t in topics]),
            )
        ).all()
    }

    # Fetch chunk counts per topic
    chunk_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(ChunkTopic.topic_id, func.count(ChunkTopic.chunk_id))
            .where(ChunkTopic.topic_id.in_([t.id for t in topics]))
            .group_by(ChunkTopic.topic_id)
        ).all()
    }

    # Diagnostic: exactly 1 question per distinct topic up to target_count
    if kind == "diagnostic":
        # Sort topics: lowest mastery first, then least recently practised, then teaching order
        def topic_sort_key(t: Topic):
            m = masteries.get(t.id)
            p_mast = m.p_mastery if m else 0.5
            last_pract = m.last_practiced_at.timestamp() if (m and m.last_practiced_at) else 0.0
            return (p_mast, last_pract, -chunk_counts.get(t.id, 0), t.id)

        sorted_topics = sorted(topics, key=topic_sort_key)
        selected_topics = sorted_topics[:target_count]
        return {t.id: 1 for t in selected_topics}

    # Mock Exam: weight allocation by chunk_count
    if kind == "mock_exam":
        total_chunks = sum(chunk_counts.get(t.id, 1) for t in topics)
        allocation: Dict[int, int] = {t.id: 0 for t in topics}
        if total_chunks == 0:
            total_chunks = len(topics)

        # Distribute proportionally using largest remainder method
        remainders = []
        assigned_total = 0
        for t in topics:
            c = chunk_counts.get(t.id, 1)
            exact = (c / total_chunks) * target_count
            base = int(exact)
            allocation[t.id] = base
            assigned_total += base
            remainders.append((exact - base, t.id))

        remainders.sort(key=lambda x: x[0], reverse=True)
        shortfall = target_count - assigned_total
        for i in range(shortfall):
            allocation[remainders[i % len(remainders)][1]] += 1
        return allocation

    # Quiz:
    # If there are more topics than target_count, prioritize topics
    if len(topics) > target_count:
        def quiz_priority_key(t: Topic):
            m = masteries.get(t.id)
            p_mast = m.p_mastery if m else 0.5
            last_pract = m.last_practiced_at.timestamp() if (m and m.last_practiced_at) else 0.0
            return (p_mast, last_pract, -chunk_counts.get(t.id, 0), t.id)

        sorted_topics = sorted(topics, key=quiz_priority_key)
        selected_topics = sorted_topics[:target_count]
        return {t.id: 1 for t in selected_topics}

    # Otherwise spread evenly across all eligible topics
    base = target_count // len(topics)
    remainder = target_count % len(topics)
    allocation: Dict[int, int] = {}
    for idx, t in enumerate(topics):
        allocation[t.id] = base + (1 if idx < remainder else 0)

    return allocation


def plan_topic_difficulty_and_qtypes(
    db: Session,
    student_id: int,
    topic: Topic,
    count: int,
    difficulty: str,
    question_types: List[str],
    kind: str,
    has_numerical: bool,
    warnings: List[str],
    offset: int = 0,
) -> Tuple[List[str], List[str]]:
    """Determine difficulty and question types for the questions assigned to this topic."""
    # 1. Difficulty planning
    difficulties: List[str] = []
    if difficulty in {"easy", "medium", "hard"}:
        difficulties = [difficulty] * count
    elif kind in {"diagnostic", "mock_exam"}:
        # 30% easy, 50% medium, 20% hard mix
        pool = ["easy", "medium", "medium", "hard", "easy", "medium", "medium", "hard", "medium", "easy"]
        difficulties = [pool[(offset + i) % len(pool)] for i in range(count)]
    else:
        # "auto" for quiz: based on student's p_mastery for this topic
        mastery = db.scalar(
            select(Mastery).where(
                Mastery.student_id == student_id,
                Mastery.topic_id == topic.id,
            )
        )
        if not mastery:
            d = "medium"
        elif mastery.p_mastery < 0.35:
            d = "easy"
        elif mastery.p_mastery <= 0.70:
            d = "medium"
        else:
            d = "hard"
        difficulties = [d] * count

    # 2. Question types planning
    # If numerical is requested but chunks lack quantitative content, fall back to short_answer
    usable_qtypes = list(question_types)
    if "numerical" in usable_qtypes and not has_numerical:
        usable_qtypes = [qt if qt != "numerical" else "short_answer" for qt in usable_qtypes]
        warn_msg = f"Topic '{topic.name}' lacks quantitative formulas/numbers; numerical questions fell back to short_answer."
        if warn_msg not in warnings:
            warnings.append(warn_msg)

    # Distribute types roughly evenly across the entire assessment
    qtypes_plan = [usable_qtypes[(offset + i) % len(usable_qtypes)] for i in range(count)]

    return difficulties, qtypes_plan


def select_topic_chunks(
    db: Session,
    student_id: int,
    course_id: int,
    topic_id: int,
) -> Tuple[List[Chunk], Dict[int, Source], List[Dict], bool]:
    """Select up to QUIZ_CONTEXT_CHUNKS for a topic, prioritizing chunks quizzed least."""
    settings = get_settings()

    # 1. Find past questions for this student to calculate chunk usage frequency
    past_questions = list(
        db.scalars(
            select(Question)
            .where(
                Question.course_id == course_id,
                Question.topic_id == topic_id,
            )
        ).all()
    )
    # Count how often each chunk id appears in source_chunk_ids
    chunk_usage: Dict[int, int] = {}
    for q in past_questions:
        for cid in q.source_chunk_ids:
            try:
                cid_int = int(cid)
                chunk_usage[cid_int] = chunk_usage.get(cid_int, 0) + 1
            except (ValueError, TypeError):
                pass

    # 2. Get chunks tagged to this topic
    chunks = list(
        db.scalars(
            select(Chunk)
            .join(ChunkTopic, ChunkTopic.chunk_id == Chunk.id)
            .where(
                ChunkTopic.topic_id == topic_id,
                Chunk.course_id == course_id,
                Chunk.embedded == True,
            )
        ).all()
    )

    if not chunks:
        return [], {}, [], False

    # 3. Sort chunks: least used by this student first, then by chunk id
    chunks.sort(key=lambda c: (chunk_usage.get(c.id, 0), c.id))

    # Prefer diversity across sources
    selected_chunks: List[Chunk] = []
    seen_sources: Set[int] = set()

    for c in chunks:
        if c.source_id not in seen_sources:
            selected_chunks.append(c)
            seen_sources.add(c.source_id)
            if len(selected_chunks) >= settings.quiz_context_chunks:
                break

    # If still below max, fill with remaining
    if len(selected_chunks) < settings.quiz_context_chunks:
        for c in chunks:
            if c not in selected_chunks:
                selected_chunks.append(c)
                if len(selected_chunks) >= settings.quiz_context_chunks:
                    break

    # 4. Fetch source records
    source_ids = {c.source_id for c in selected_chunks}
    source_map = {
        s.id: s
        for s in db.scalars(select(Source).where(Source.id.in_(source_ids))).all()
    }

    # 5. Build citation summaries and detect quantitative content
    chunk_citations: List[Dict] = []
    has_numerical = False

    for c in selected_chunks:
        src = source_map.get(c.source_id)
        if src:
            cit = build_citation(c, src)
            chunk_citations.append(cit.model_dump())
        if NUMERICAL_INDICATORS.search(c.text):
            has_numerical = True

    return selected_chunks, source_map, chunk_citations, has_numerical


def prepare_topic_contexts(
    db: Session,
    course_id: int,
    student_id: int,
    topics: List[Topic],
    allocation: Dict[int, int],
    difficulty: str,
    question_types: List[str],
    kind: str,
    warnings: List[str],
) -> List[TopicContext]:
    """Prepare the complete TopicContext objects for all assigned topics."""
    contexts: List[TopicContext] = []
    global_q_offset = 0

    # Map parent topics
    parent_ids = {t.parent_id for t in topics if t.parent_id is not None}
    parent_map = (
        {p.id: p for p in db.scalars(select(Topic).where(Topic.id.in_(parent_ids))).all()}
        if parent_ids
        else {}
    )

    for t in topics:
        count = allocation.get(t.id, 0)
        if count <= 0:
            continue

        concepts = list(
            db.scalars(
                select(Concept)
                .where(Concept.topic_id == t.id)
                .order_by(Concept.id.asc())
            ).all()
        )

        chunks, source_map, chunk_cits, has_num = select_topic_chunks(
            db=db,
            student_id=student_id,
            course_id=course_id,
            topic_id=t.id,
        )

        diffs, qtypes = plan_topic_difficulty_and_qtypes(
            db=db,
            student_id=student_id,
            topic=t,
            count=count,
            difficulty=difficulty,
            question_types=question_types,
            kind=kind,
            has_numerical=has_num,
            warnings=warnings,
            offset=global_q_offset,
        )
        global_q_offset += count

        contexts.append(
            TopicContext(
                topic=t,
                parent_topic=parent_map.get(t.parent_id) if t.parent_id else None,
                concepts=concepts,
                chunks=chunks,
                source_map=source_map,
                chunk_citations=chunk_cits,
                requested_count=count,
                assigned_qtypes=qtypes,
                assigned_difficulties=diffs,
                has_numerical_support=has_num,
            )
        )

    return contexts
