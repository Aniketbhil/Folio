"""Assessment submission and comprehensive performance report generation."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError
from app.models.assessment import Assessment, Attempt, Question
from app.models.mastery import Mastery, MasteryEvent
from app.models.source import Chunk, Source
from app.models.topic import Topic
from app.services.citations import build_citation
from app.services.grading.prompts import (
    MISCONCEPTION_SUMMARY_SYSTEM_PROMPT,
    MISCONCEPTION_SUMMARY_USER_PROMPT,
)
from app.services.grading.schemas import MisconceptionSummary
from app.services.learner.mastery import status_for
from app.services.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


def generate_misconception_summary(
    llm: LLMClient,
    attempts: List[Attempt],
    questions: List[Question],
    topic_map: Dict[int, Topic],
) -> List[Dict[str, Any]]:
    """Synthesize student misconceptions across assessment attempts."""
    qid_to_q = {q.id: q for q in questions}
    raw_items: List[Dict[str, Any]] = []

    for att in attempts:
        if att.misconception:
            q = qid_to_q.get(att.question_id)
            if q:
                raw_items.append({
                    "topic_id": q.topic_id,
                    "text": att.misconception,
                })

    if not raw_items:
        return []

    # Exactly 1 misconception: return as-is
    if len(raw_items) == 1:
        item = raw_items[0]
        top = topic_map.get(item["topic_id"])
        return [{
            "topic": {"id": item["topic_id"], "name": top.name if top else "Topic"},
            "text": item["text"],
            "count": 1,
        }]

    # In mock mode or offline: group identical texts by topic
    from app.core.config import get_settings
    settings = get_settings()

    if settings.llm_mock:
        grouped: Dict[tuple, int] = {}
        for item in raw_items:
            key = (item["topic_id"], item["text"])
            grouped[key] = grouped.get(key, 0) + 1

        result = []
        for (tid, text), count in list(grouped.items())[:5]:
            top = topic_map.get(tid)
            result.append({
                "topic": {"id": tid, "name": top.name if top else "Topic"},
                "text": text,
                "count": count,
            })
        return result

    # Live mode: call LLM to merge near-duplicates
    allowed_topic_ids = {item["topic_id"] for item in raw_items}
    misc_text_lines = [
        f"- [Topic {item['topic_id']}] {item['text']}" for item in raw_items
    ]
    prompt = MISCONCEPTION_SUMMARY_USER_PROMPT.format(
        misconceptions_text="\n".join(misc_text_lines),
        allowed_topic_ids=", ".join(str(tid) for tid in allowed_topic_ids),
    )

    try:
        summary_out: MisconceptionSummary = llm.generate_json(
            prompt=prompt,
            schema=MisconceptionSummary,
            system=MISCONCEPTION_SUMMARY_SYSTEM_PROMPT,
            max_retries=2,
        )
        filtered = []
        for it in summary_out.items[:5]:
            if it.topic_id in allowed_topic_ids:
                top = topic_map.get(it.topic_id)
                filtered.append({
                    "topic": {"id": it.topic_id, "name": top.name if top else "Topic"},
                    "text": it.text,
                    "count": max(1, it.count),
                })
        if filtered:
            return filtered
    except Exception as exc:
        logger.warning("Misconception summary LLM call failed: %s", exc)

    # Fallback to simple grouping
    grouped = {}
    for item in raw_items:
        key = (item["topic_id"], item["text"])
        grouped[key] = grouped.get(key, 0) + 1
    return [
        {
            "topic": {"id": tid, "name": topic_map[tid].name if tid in topic_map else "Topic"},
            "text": text,
            "count": count,
        }
        for (tid, text), count in list(grouped.items())[:5]
    ]


def build_report(db: Session, assessment: Assessment) -> Dict[str, Any]:
    """Build the comprehensive assessment report from database state."""
    if assessment.status != "submitted":
        raise AppError(
            "Assessment has not been submitted yet.",
            code="not_submitted",
            status_code=409,
        )

    # 1. Fetch questions and attempts
    questions = list(
        db.scalars(
            select(Question)
            .where(Question.assessment_id == assessment.id)
            .order_by(Question.position.asc())
        ).all()
    )
    attempts = list(
        db.scalars(
            select(Attempt).where(Attempt.assessment_id == assessment.id)
        ).all()
    )
    attempts_by_qid = {att.question_id: att for att in attempts}

    # 2. Fetch all topics and parents involved
    topic_ids = list({q.topic_id for q in questions})
    topics = list(db.scalars(select(Topic).where(Topic.id.in_(topic_ids))).all()) if topic_ids else []
    topic_map = {t.id: t for t in topics}

    parent_ids = [t.parent_id for t in topics if t.parent_id is not None]
    parent_map = {}
    if parent_ids:
        parents = list(db.scalars(select(Topic).where(Topic.id.in_(parent_ids))).all())
        parent_map = {p.id: p for p in parents}

    # 3. Summary metrics
    total_questions = len(questions)
    answered = len(attempts)
    correct = sum(1 for att in attempts if att.is_correct)
    skipped = total_questions - answered
    times = [att.time_taken_sec for att in attempts if att.time_taken_sec is not None]
    avg_time_sec = round(sum(times) / len(times), 1) if times else None
    total_time_sec = round(sum(times), 1) if times else None
    score_val = float(assessment.score) if assessment.score is not None else 0.0
    score_pct = round(score_val * 100.0, 1)

    # 4. By Topic Breakdown
    by_topic: List[Dict[str, Any]] = []
    for tid in topic_ids:
        top = topic_map.get(tid)
        top_name = top.name if top else "Topic"
        p_id = top.parent_id if top else None
        p_name = parent_map[p_id].name if (p_id and p_id in parent_map) else None

        t_questions = [q for q in questions if q.topic_id == tid]
        t_attempts = [attempts_by_qid[q.id] for q in t_questions if q.id in attempts_by_qid]
        t_answered = len(t_attempts)
        t_correct = sum(1 for att in t_attempts if att.is_correct)
        t_acc = round(t_correct / t_answered, 2) if t_answered > 0 else 0.0

        # Query MasteryEvents for this assessment's attempts on this topic
        m_events = list(
            db.scalars(
                select(MasteryEvent)
                .join(Attempt, Attempt.id == MasteryEvent.attempt_id)
                .where(
                    Attempt.assessment_id == assessment.id,
                    MasteryEvent.topic_id == tid,
                )
                .order_by(MasteryEvent.id.asc())
            ).all()
        )

        m_row = db.scalar(
            select(Mastery).where(
                Mastery.student_id == assessment.student_id,
                Mastery.topic_id == tid,
            )
        )

        if m_events:
            mastery_before = round(m_events[0].p_before, 4)
            mastery_after = round(m_events[-1].p_after, 4)
        elif m_row:
            mastery_before = round(m_row.p_mastery, 4)
            mastery_after = round(m_row.p_mastery, 4)
        else:
            mastery_before = 0.30
            mastery_after = 0.30

        status_str = status_for(m_row.p_mastery, m_row.attempts_count) if m_row else "new"

        by_topic.append({
            "topic": {
                "id": tid,
                "name": top_name,
                "parent_id": p_id,
                "parent_name": p_name,
            },
            "questions": len(t_questions),
            "answered": t_answered,
            "correct": t_correct,
            "accuracy": t_acc,
            "mastery_before": mastery_before,
            "mastery_after": mastery_after,
            "status": status_str,
        })

    # Weak topics: accuracy < 0.6 or status "weak"; ordered by mastery_after ascending
    weak_topics = [
        item for item in by_topic
        if item["accuracy"] < 0.6 or item["status"] == "weak"
    ]
    weak_topics.sort(key=lambda x: x["mastery_after"])

    # Strong topics: accuracy >= 0.8 and status not weak
    strong_topics = [
        item for item in by_topic
        if item["accuracy"] >= 0.8 and item["status"] != "weak"
    ]

    # 5. By Difficulty Breakdown
    by_diff_map: Dict[str, Dict[str, int]] = {
        d: {"answered": 0, "correct": 0} for d in ["easy", "medium", "hard"]
    }
    for q in questions:
        diff = q.difficulty.lower()
        if diff in by_diff_map and q.id in attempts_by_qid:
            att = attempts_by_qid[q.id]
            by_diff_map[diff]["answered"] += 1
            if att.is_correct:
                by_diff_map[diff]["correct"] += 1

    by_difficulty = [
        {"difficulty": d, "answered": by_diff_map[d]["answered"], "correct": by_diff_map[d]["correct"]}
        for d in ["easy", "medium", "hard"]
    ]

    # 6. By Type Breakdown
    by_type_map: Dict[str, Dict[str, int]] = {
        t: {"answered": 0, "correct": 0} for t in ["mcq", "short_answer", "numerical"]
    }
    for q in questions:
        qt = q.qtype.lower()
        if qt in by_type_map and q.id in attempts_by_qid:
            att = attempts_by_qid[q.id]
            by_type_map[qt]["answered"] += 1
            if att.is_correct:
                by_type_map[qt]["correct"] += 1

    by_type = [
        {"qtype": qt, "answered": by_type_map[qt]["answered"], "correct": by_type_map[qt]["correct"]}
        for t, qt in [("mcq", "mcq"), ("short_answer", "short_answer"), ("numerical", "numerical")]
    ]

    # 7. Misconceptions
    cached_report = assessment.config.get("report", {}) if assessment.config else {}
    misconceptions = cached_report.get("misconceptions", [])

    # 8. Detailed Review List
    review: List[Dict[str, Any]] = []
    for q in questions:
        att = attempts_by_qid.get(q.id)
        top = topic_map.get(q.topic_id)

        # Format correct answer
        qtype = q.qtype.lower()
        if qtype == "mcq":
            corr_key = q.correct_answer.strip().upper()
            corr_text = corr_key
            for opt in (q.options or []):
                if opt.get("key", "").upper() == corr_key:
                    corr_text = opt.get("text", "")
                    break
            formatted_correct = {"key": corr_key, "text": corr_text}
        elif qtype == "numerical":
            unit = (q.meta or {}).get("unit")
            try:
                num_val = float(q.correct_answer)
            except ValueError:
                num_val = 0.0
            formatted_correct = {"value": num_val, "unit": unit}
        else:
            formatted_correct = {"text": q.correct_answer}

        review.append({
            "question_id": q.id,
            "position": q.position,
            "qtype": q.qtype,
            "difficulty": q.difficulty,
            "prompt": q.prompt,
            "options": q.options,
            "topic": {"id": q.topic_id, "name": top.name if top else "Topic"},
            "your_answer": att.answer if att else None,
            "answered": att is not None,
            "correct_answer": formatted_correct,
            "is_correct": att.is_correct if att else None,
            "score": att.score if att else None,
            "explanation": q.explanation,
            "feedback": att.feedback if att else None,
            "misconception": att.misconception if att else None,
            "citations": att.citations if att else [],
        })

    # 9. Recommended Next Steps (up to 5 items, weakest topics first)
    recommended_next_steps: List[Dict[str, Any]] = []
    topics_for_recommendations = weak_topics if weak_topics else sorted(by_topic, key=lambda x: x["accuracy"])
    misc_by_topic_id = {m["topic"]["id"]: m["text"] for m in misconceptions if "topic" in m and "id" in m["topic"]}

    # Collect missed chunks per topic
    missed_chunk_ids_by_topic: Dict[int, List[int]] = {}
    for q in questions:
        att = attempts_by_qid.get(q.id)
        if (att is None or not att.is_correct) and q.source_chunk_ids:
            missed_chunk_ids_by_topic.setdefault(q.topic_id, []).extend(q.source_chunk_ids)

    # Preload missed chunks and sources
    all_missed_cids = list({cid for cids in missed_chunk_ids_by_topic.values() for cid in cids})
    chunk_cache: Dict[int, Chunk] = {}
    source_cache: Dict[int, Source] = {}
    if all_missed_cids:
        c_list = list(db.scalars(select(Chunk).where(Chunk.id.in_(all_missed_cids))).all())
        chunk_cache = {c.id: c for c in c_list}
        s_ids = list({c.source_id for c in c_list})
        if s_ids:
            s_list = list(db.scalars(select(Source).where(Source.id.in_(s_ids))).all())
            source_cache = {s.id: s for s in s_list}

    for item in topics_for_recommendations[:5]:
        tid = item["topic"]["id"]
        tname = item["topic"]["name"]
        acc = item["accuracy"]

        # Citations up to 2
        rec_citations = []
        cids = list(dict.fromkeys(missed_chunk_ids_by_topic.get(tid, [])))[:2]
        for cid in cids:
            chk = chunk_cache.get(cid)
            if chk:
                src = source_cache.get(chk.source_id)
                if src:
                    cit = build_citation(chk, src)
                    rec_citations.append(cit.model_dump())

        if tid in misc_by_topic_id:
            rec_type = "ask_tutor"
            reason = f"You had a misconception on {tname}: {misc_by_topic_id[tid]}"
        elif acc < 0.5:
            rec_type = "review_source"
            reason = f"Review the source material for {tname} (accuracy {int(acc * 100)}%)."
        else:
            rec_type = "practice_topic"
            reason = f"Practice more questions on {tname} to reinforce understanding."

        recommended_next_steps.append({
            "type": rec_type,
            "topic": {"id": tid, "name": tname},
            "reason": reason,
            "citations": rec_citations,
        })

    # 10. Diagnostic Note
    diagnostic_note = None
    if assessment.kind == "diagnostic":
        diagnostic_note = f"Your starting level was estimated across {len(by_topic)} topics."

    return {
        "assessment": {
            "id": assessment.id,
            "kind": assessment.kind,
            "title": assessment.title,
            "course_id": assessment.course_id,
            "student_id": assessment.student_id,
            "submitted_at": assessment.submitted_at,
        },
        "summary": {
            "score": score_val,
            "score_pct": score_pct,
            "total_questions": total_questions,
            "answered": answered,
            "correct": correct,
            "skipped": skipped,
            "avg_time_sec": avg_time_sec,
            "total_time_sec": total_time_sec,
        },
        "by_topic": by_topic,
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "by_difficulty": by_difficulty,
        "by_type": by_type,
        "misconceptions": misconceptions,
        "review": review,
        "recommended_next_steps": recommended_next_steps,
        "diagnostic_note": diagnostic_note,
    }


def submit_assessment(db: Session, assessment_id: int) -> Dict[str, Any]:
    """Submit an in-progress assessment, calculate final score, and generate report."""
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise AppError("Assessment not found.", code="assessment_not_found", status_code=404)

    # Idempotent return if already submitted
    if assessment.status == "submitted":
        return build_report(db, assessment)

    questions = list(
        db.scalars(
            select(Question)
            .where(Question.assessment_id == assessment.id)
            .order_by(Question.position.asc())
        ).all()
    )
    attempts = list(
        db.scalars(
            select(Attempt).where(Attempt.assessment_id == assessment.id)
        ).all()
    )

    if not attempts:
        raise AppError(
            "Answer at least one question before submitting.",
            code="no_answers",
            status_code=409,
        )

    # Calculate final score: sum(scores) / total_questions
    total_q_count = len(questions) if questions else 1
    sum_scores = sum(att.score for att in attempts)
    final_score = round(sum_scores / total_q_count, 4)

    assessment.score = final_score
    assessment.status = "submitted"
    assessment.submitted_at = datetime.now(timezone.utc)

    # Synthesize misconceptions
    topic_ids = list({q.topic_id for q in questions})
    topics = list(db.scalars(select(Topic).where(Topic.id.in_(topic_ids))).all()) if topic_ids else []
    topic_map = {t.id: t for t in topics}

    llm = get_llm_client()
    misc_summary = generate_misconception_summary(
        llm=llm,
        attempts=attempts,
        questions=questions,
        topic_map=topic_map,
    )

    if assessment.config is None:
        assessment.config = {}
    cfg = dict(assessment.config)
    cfg["report"] = {
        "misconceptions": misc_summary,
        "submitted_at": assessment.submitted_at.isoformat(),
        "final_score": final_score,
    }
    assessment.config = cfg
    flag_modified(assessment, "config")

    db.commit()
    db.refresh(assessment)

    return build_report(db, assessment)
