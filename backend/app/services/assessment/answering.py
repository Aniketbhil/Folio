"""Service handling student question answers, grading, and atomic mastery updates."""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.assessment import Assessment, Attempt, Question
from app.models.mastery import MasteryEvent
from app.models.source import Chunk, Source
from app.models.topic import Topic
from app.services.grading.grader import GradingService
from app.services.learner.mastery import apply_attempt

logger = logging.getLogger(__name__)


class AnswerService:
    """Orchestrates question answering, grading, and mastery updates."""

    @staticmethod
    def submit_answer(
        db: Session,
        assessment_id: int,
        question_id: int,
        answer: str,
        time_taken_sec: Optional[float] = None,
        student_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Submit and grade a student's answer to an assessment question."""
        # 1. Validation checks on assessment and question
        assessment = db.get(Assessment, assessment_id)
        if not assessment:
            raise AppError("Assessment not found.", code="assessment_not_found", status_code=404)

        question = db.get(Question, question_id)
        if not question or question.assessment_id != assessment.id:
            raise AppError("Question not found in this assessment.", code="question_not_found", status_code=404)

        if assessment.status != "in_progress":
            raise AppError("Assessment already submitted.", code="invalid_state", status_code=409)

        if student_id is not None and student_id != assessment.student_id:
            raise AppError("Student does not have access to this assessment.", code="forbidden_student", status_code=403)

        # Check if already answered
        existing_attempt = db.scalar(
            select(Attempt).where(Attempt.question_id == question.id)
        )
        if existing_attempt:
            raise AppError("Question has already been answered.", code="already_answered", status_code=409)

        # Validate answer content
        if not isinstance(answer, str) or not answer.strip():
            raise AppError("Answer cannot be empty.", code="invalid_answer", status_code=422)

        answer_str = answer.strip()
        if len(answer_str) > 2000:
            raise AppError("Answer exceeds maximum length of 2000 characters.", code="invalid_answer", status_code=422)

        if time_taken_sec is not None:
            if time_taken_sec < 0.0 or time_taken_sec > 36000.0:
                raise AppError("time_taken_sec must be between 0 and 36000.", code="validation_error", status_code=422)

        # 2. Retrieve chunks for cited sources (read-only query)
        chunks: list[Chunk] = []
        source_map: dict[int, Source] = {}
        if question.source_chunk_ids:
            chunks = list(
                db.scalars(
                    select(Chunk).where(Chunk.id.in_(question.source_chunk_ids))
                ).all()
            )
            src_ids = list({c.source_id for c in chunks})
            if src_ids:
                source_map = {
                    s.id: s
                    for s in db.scalars(select(Source).where(Source.id.in_(src_ids))).all()
                }

        # 3. Grade outside any write locks or open transactions
        grader = GradingService()
        grade_result = grader.grade(
            question=question,
            answer=answer_str,
            chunks=chunks,
            source_map=source_map,
        )

        # 4. Atomic write transaction: insert Attempt and update Mastery
        try:
            origin = "diagnostic" if assessment.kind == "diagnostic" else "quiz"
            mastery_res = apply_attempt(
                db=db,
                student_id=assessment.student_id,
                topic_id=question.topic_id,
                score=grade_result.score,
                qtype=question.qtype,
                difficulty=question.difficulty,
                origin=origin,
                attempt_id=None,
                is_correct=grade_result.is_correct,
            )

            attempt = Attempt(
                student_id=assessment.student_id,
                question_id=question.id,
                assessment_id=assessment.id,
                answer=answer_str,
                is_correct=grade_result.is_correct,
                score=grade_result.score,
                feedback=grade_result.feedback,
                citations=grade_result.citations,
                misconception=grade_result.misconception,
                time_taken_sec=time_taken_sec,
                meta=grade_result.meta,
            )
            db.add(attempt)
            db.flush()

            # Backfill attempt_id on MasteryEvent
            if mastery_res.get("event_id"):
                db.execute(
                    update(MasteryEvent)
                    .where(MasteryEvent.id == mastery_res["event_id"])
                    .values(attempt_id=attempt.id)
                )

            db.commit()
            db.refresh(attempt)
        except IntegrityError:
            db.rollback()
            raise AppError("Question has already been answered.", code="already_answered", status_code=409)
        except Exception:
            db.rollback()
            raise

        # 5. Format correct answer representation
        qtype = question.qtype.lower()
        if qtype == "mcq":
            corr_key = question.correct_answer.strip().upper()
            corr_text = corr_key
            for opt in (question.options or []):
                if opt.get("key", "").upper() == corr_key:
                    corr_text = opt.get("text", "")
                    break
            formatted_correct_answer = {"key": corr_key, "text": corr_text}
        elif qtype == "short_answer":
            formatted_correct_answer = {"text": question.correct_answer}
        elif qtype == "numerical":
            unit = (question.meta or {}).get("unit")
            try:
                num_val = float(question.correct_answer)
            except ValueError:
                num_val = 0.0
            formatted_correct_answer = {"value": num_val, "unit": unit}
        else:
            formatted_correct_answer = {"text": question.correct_answer}

        # 6. Compute progress and topic info
        answered_count = db.scalar(
            select(func.count(Attempt.id)).where(Attempt.assessment_id == assessment.id)
        ) or 0
        total_questions = db.scalar(
            select(func.count(Question.id)).where(Question.assessment_id == assessment.id)
        ) or 0

        topic = db.get(Topic, question.topic_id)
        topic_name = topic.name if topic else "Topic"

        return {
            "attempt_id": attempt.id,
            "question_id": question.id,
            "is_correct": grade_result.is_correct,
            "score": grade_result.score,
            "correct_answer": formatted_correct_answer,
            "explanation": question.explanation,
            "feedback": grade_result.feedback,
            "citations": grade_result.citations,
            "misconception": grade_result.misconception,
            "key_points_hit": grade_result.meta.get("key_points_hit"),
            "key_points_missing": grade_result.meta.get("key_points_missing"),
            "mastery_update": {
                "topic": {"id": question.topic_id, "name": topic_name},
                "before": mastery_res["before"],
                "after": mastery_res["after"],
                "status_before": mastery_res["status_before"],
                "status_after": mastery_res["status_after"],
            },
            "progress": {
                "answered": answered_count,
                "total": total_questions,
            },
        }
