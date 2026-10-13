"""Grading service evaluating student answers with rubric, numerical, and MCQ rules."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.assessment import Question
from app.models.source import Chunk, Source
from app.schemas.tutor import TutorCitation
from app.services.citations import build_citation
from app.services.grading.numeric import grade_numeric, parse_number
from app.services.grading.prompts import (
    SHORT_ANSWER_GRADING_SYSTEM_PROMPT,
    SHORT_ANSWER_GRADING_USER_PROMPT,
    WRONG_ANSWER_DIAGNOSIS_SYSTEM_PROMPT,
    WRONG_ANSWER_DIAGNOSIS_USER_PROMPT,
)
from app.services.grading.schemas import ShortAnswerGrade, WrongAnswerDiagnosis
from app.services.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
    "of", "with", "and", "or", "by", "that", "this", "it", "as", "be", "from",
    "which", "who", "whom", "whose", "what", "where", "when", "why", "how",
}


@dataclass
class GradeResult:
    """Result of grading a student's answer."""

    score: float
    is_correct: bool
    feedback: str
    misconception: Optional[str]
    meta: Dict[str, Any]
    graded_by: str  # "rule" | "llm" | "mock"
    citations: List[Dict[str, Any]]


def normalize_mcq_answer(answer: str, options: Optional[List[Dict[str, Any]]]) -> str:
    """Normalize user's MCQ answer to an uppercase option letter (e.g. 'A').

    Accepts:
    - 'a', 'A', 'A.', 'a)', '(A)'
    - Exact match on option text (case-insensitive)

    Raises:
        AppError(422, 'invalid_answer') if the answer does not map to a valid option.
    """
    clean = answer.strip()
    if not clean:
        raise AppError(
            "Please select a valid option letter (A, B, C, or D).",
            code="invalid_answer",
            status_code=422,
        )

    # 1. Check if it starts with or is a single letter option
    letter_match = re.match(r"^\(?([a-dA-D])[\.\)]?$", clean)
    if letter_match:
        return letter_match.group(1).upper()

    # 2. Check if clean matches an option key exactly
    if options:
        opt_keys = {opt.get("key", "").upper() for opt in options}
        if clean.upper() in opt_keys:
            return clean.upper()

        # 3. Check if clean matches option text exactly (case-insensitive)
        clean_lower = clean.lower()
        for opt in options:
            if opt.get("text", "").strip().lower() == clean_lower:
                return opt.get("key", "").upper()

    raise AppError(
        "Please select a valid option letter (A, B, C, or D).",
        code="invalid_answer",
        status_code=422,
    )


def clean_feedback_citations(feedback: str, max_ref: int, max_chars: int) -> str:
    """Strip out-of-range [n] citation markers and truncate feedback to max_chars."""
    # 1. Strip out-of-range markers
    def filter_marker(match: re.Match) -> str:
        ref_num = int(match.group(1))
        if 1 <= ref_num <= max_ref:
            return match.group(0)
        return ""

    cleaned = re.sub(r"\[(\d+)\]", filter_marker, feedback)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    # 2. Truncate at word boundary if exceeding max_chars
    if len(cleaned) > max_chars:
        truncated = cleaned[:max_chars]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        cleaned = truncated.rstrip(".,;:- ") + "..."

    return cleaned


class GradingService:
    """Service evaluating student answers using rules, mock algorithms, or LLMs."""

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm or get_llm_client()

    def grade(
        self,
        question: Question,
        answer: str,
        chunks: List[Chunk],
        source_map: Dict[int, Source],
    ) -> GradeResult:
        """Grade student answer according to question type and system settings."""
        settings = get_settings()

        # 1. Build TutorCitation list for cited chunks
        citations_out: List[Dict[str, Any]] = []
        for idx, cid in enumerate(question.source_chunk_ids, start=1):
            chunk = next((c for c in chunks if c.id == cid), None)
            if chunk:
                src = source_map.get(chunk.source_id)
                if src:
                    cit = build_citation(chunk, src)
                    tutor_cit = TutorCitation(ref=idx, **cit.model_dump())
                    citations_out.append(tutor_cit.model_dump())

        # Format sources text for LLM prompts if needed
        sources_text_blocks = []
        for idx, cit in enumerate(citations_out, start=1):
            sources_text_blocks.append(f"[{idx}] {cit['source_title']}:\n{cit['snippet']}")
        sources_prompt_str = "\n\n".join(sources_text_blocks)

        qtype = question.qtype.lower()

        # -------------------------------------------------------------
        # MCQ Grading
        # -------------------------------------------------------------
        if qtype == "mcq":
            options = question.options or []
            chosen_letter = normalize_mcq_answer(answer, options)
            correct_letter = question.correct_answer.strip().upper()

            # Find option texts
            chosen_opt_text = chosen_letter
            correct_opt_text = correct_letter
            for opt in options:
                if opt.get("key", "").upper() == chosen_letter:
                    chosen_opt_text = opt.get("text", "")
                if opt.get("key", "").upper() == correct_letter:
                    correct_opt_text = opt.get("text", "")

            if chosen_letter == correct_letter:
                # Correct MCQ: No LLM call!
                feedback = clean_feedback_citations(
                    question.explanation,
                    len(citations_out),
                    settings.feedback_max_chars,
                )
                return GradeResult(
                    score=1.0,
                    is_correct=True,
                    feedback=feedback,
                    misconception=None,
                    meta={"chosen_letter": chosen_letter},
                    graded_by="rule",
                    citations=citations_out,
                )
            else:
                # Wrong MCQ
                if settings.llm_mock:
                    feedback_raw = (
                        f"The correct answer is {correct_letter}: '{correct_opt_text}'. "
                        f"{question.explanation}"
                    )
                    feedback = clean_feedback_citations(
                        feedback_raw,
                        len(citations_out),
                        settings.feedback_max_chars,
                    )
                    misconception = f"(mock) Confused '{chosen_opt_text}' with '{correct_opt_text}'."
                    return GradeResult(
                        score=0.0,
                        is_correct=False,
                        feedback=feedback,
                        misconception=misconception,
                        meta={"chosen_letter": chosen_letter},
                        graded_by="mock",
                        citations=citations_out,
                    )
                else:
                    # Live LLM Diagnosis
                    options_str = "\n".join(
                        f"({opt.get('key')}) {opt.get('text')}" for opt in options
                    )
                    diag_prompt = WRONG_ANSWER_DIAGNOSIS_USER_PROMPT.format(
                        prompt=question.prompt,
                        options_text=f"Options:\n{options_str}",
                        correct_answer_text=f"({correct_letter}) {correct_opt_text}",
                        explanation=question.explanation,
                        student_answer_text=f"({chosen_letter}) {chosen_opt_text}",
                        sources_text=sources_prompt_str,
                    )
                    try:
                        diag_res: WrongAnswerDiagnosis = self.llm.generate_json(
                            prompt=diag_prompt,
                            schema=WrongAnswerDiagnosis,
                            system=WRONG_ANSWER_DIAGNOSIS_SYSTEM_PROMPT,
                            max_retries=2,
                        )
                        feedback = clean_feedback_citations(
                            diag_res.feedback,
                            len(citations_out),
                            settings.feedback_max_chars,
                        )
                        return GradeResult(
                            score=0.0,
                            is_correct=False,
                            feedback=feedback,
                            misconception=diag_res.misconception,
                            meta={"chosen_letter": chosen_letter},
                            graded_by="llm",
                            citations=citations_out,
                        )
                    except Exception as exc:
                        logger.warning("MCQ wrong diagnosis LLM failed: %s", exc)
                        fallback_feedback = clean_feedback_citations(
                            f"The correct answer is {correct_letter}: '{correct_opt_text}'. {question.explanation}",
                            len(citations_out),
                            settings.feedback_max_chars,
                        )
                        return GradeResult(
                            score=0.0,
                            is_correct=False,
                            feedback=fallback_feedback,
                            misconception=None,
                            meta={"chosen_letter": chosen_letter},
                            graded_by="rule",
                            citations=citations_out,
                        )

        # -------------------------------------------------------------
        # Numerical Grading
        # -------------------------------------------------------------
        if qtype == "numerical":
            parsed_num = parse_number(answer)
            if parsed_num is None:
                raise AppError(
                    "Please enter a number, optionally with a unit.",
                    code="invalid_answer",
                    status_code=422,
                )

            expected_val = float(question.correct_answer)
            tol_pct = float(question.meta.get("tolerance_pct", 1.0)) if question.meta else 1.0
            unit = question.meta.get("unit") if question.meta else None

            num_score, _ = grade_numeric(answer, expected_val, tol_pct)
            is_corr = num_score >= 1.0
            meta_dict = {
                "parsed_value": parsed_num,
                "expected_value": expected_val,
                "tolerance_pct": tol_pct,
            }

            if is_corr:
                # Correct Numerical: No LLM call!
                feedback = clean_feedback_citations(
                    question.explanation,
                    len(citations_out),
                    settings.feedback_max_chars,
                )
                return GradeResult(
                    score=1.0,
                    is_correct=True,
                    feedback=feedback,
                    misconception=None,
                    meta=meta_dict,
                    graded_by="rule",
                    citations=citations_out,
                )
            else:
                # Wrong Numerical
                expected_display = f"{expected_val} {unit}" if unit else str(expected_val)
                parsed_display = f"{parsed_num} {unit}" if unit else str(parsed_num)

                if settings.llm_mock:
                    feedback_raw = (
                        f"The correct value is {expected_display}. {question.explanation}"
                    )
                    feedback = clean_feedback_citations(
                        feedback_raw,
                        len(citations_out),
                        settings.feedback_max_chars,
                    )
                    misconception = f"(mock) Expected {expected_display}, got {parsed_display}."
                    return GradeResult(
                        score=0.0,
                        is_correct=False,
                        feedback=feedback,
                        misconception=misconception,
                        meta=meta_dict,
                        graded_by="mock",
                        citations=citations_out,
                    )
                else:
                    # Live LLM Diagnosis
                    diag_prompt = WRONG_ANSWER_DIAGNOSIS_USER_PROMPT.format(
                        prompt=question.prompt,
                        options_text="",
                        correct_answer_text=expected_display,
                        explanation=question.explanation,
                        student_answer_text=parsed_display,
                        sources_text=sources_prompt_str,
                    )
                    try:
                        diag_res = self.llm.generate_json(
                            prompt=diag_prompt,
                            schema=WrongAnswerDiagnosis,
                            system=WRONG_ANSWER_DIAGNOSIS_SYSTEM_PROMPT,
                            max_retries=2,
                        )
                        feedback = clean_feedback_citations(
                            diag_res.feedback,
                            len(citations_out),
                            settings.feedback_max_chars,
                        )
                        return GradeResult(
                            score=0.0,
                            is_correct=False,
                            feedback=feedback,
                            misconception=diag_res.misconception,
                            meta=meta_dict,
                            graded_by="llm",
                            citations=citations_out,
                        )
                    except Exception as exc:
                        logger.warning("Numerical wrong diagnosis LLM failed: %s", exc)
                        fallback_feedback = clean_feedback_citations(
                            f"The correct value is {expected_display}. {question.explanation}",
                            len(citations_out),
                            settings.feedback_max_chars,
                        )
                        return GradeResult(
                            score=0.0,
                            is_correct=False,
                            feedback=fallback_feedback,
                            misconception=None,
                            meta=meta_dict,
                            graded_by="rule",
                            citations=citations_out,
                        )

        # -------------------------------------------------------------
        # Short Answer Grading
        # -------------------------------------------------------------
        key_points: List[str] = (question.meta or {}).get("key_points", [])
        if not key_points:
            # Fallback rubric: split correct answer into sentences
            raw_sents = [s.strip() for s in re.split(r"[.!?]", question.correct_answer) if s.strip()]
            key_points = raw_sents or [question.correct_answer]

        if settings.llm_mock:
            # Deterministic mock grading
            clean_ans_lower = answer.lower()
            hits: List[str] = []
            missing: List[str] = []

            for kp in key_points:
                words = [
                    w for w in re.findall(r"[a-zA-Z0-9]+", kp.lower())
                    if w not in STOPWORDS and len(w) > 2
                ]
                if not words:
                    words = [kp.lower()]
                matching = [w for w in words if w in clean_ans_lower]
                if (len(matching) / len(words)) >= 0.5:
                    hits.append(kp)
                else:
                    missing.append(kp)

            sa_score = len(hits) / max(1, len(key_points))
            sa_score = round(max(0.0, min(1.0, sa_score)), 2)
            is_corr = sa_score >= settings.grade_correct_threshold
            misconception = (
                f"(mock) Missing: {missing[0]}"
                if (missing and not is_corr)
                else None
            )

            feedback_raw = (
                f"Your answer addressed {len(hits)} of {len(key_points)} key points. "
                f"Model explanation: {question.explanation}"
            )
            feedback = clean_feedback_citations(
                feedback_raw,
                len(citations_out),
                settings.feedback_max_chars,
            )
            return GradeResult(
                score=sa_score,
                is_correct=is_corr,
                feedback=feedback,
                misconception=misconception,
                meta={
                    "key_points_hit": hits,
                    "key_points_missing": missing,
                },
                graded_by="mock",
                citations=citations_out,
            )
        else:
            # Live LLM Short Answer Grading
            rubric_str = "\n".join(f"- {kp}" for kp in key_points)
            grading_prompt = SHORT_ANSWER_GRADING_USER_PROMPT.format(
                prompt=question.prompt,
                model_answer=question.correct_answer,
                key_points=rubric_str,
                sources_text=sources_prompt_str,
                student_answer=answer,
            )
            try:
                sa_result: ShortAnswerGrade = self.llm.generate_json(
                    prompt=grading_prompt,
                    schema=ShortAnswerGrade,
                    system=SHORT_ANSWER_GRADING_SYSTEM_PROMPT,
                    max_retries=2,
                )
            except Exception as exc:
                logger.error("Short answer grading LLM call failed: %s", exc)
                raise AppError(
                    "Couldn't grade this answer right now. Please try again.",
                    code="grading_failed",
                    status_code=502,
                )

            clamped_score = round(max(0.0, min(1.0, float(sa_result.score))), 2)
            is_corr = clamped_score >= settings.grade_correct_threshold
            feedback = clean_feedback_citations(
                sa_result.feedback,
                len(citations_out),
                settings.feedback_max_chars,
            )
            return GradeResult(
                score=clamped_score,
                is_correct=is_corr,
                feedback=feedback,
                misconception=sa_result.misconception,
                meta={
                    "key_points_hit": sa_result.key_points_hit,
                    "key_points_missing": sa_result.key_points_missing,
                },
                graded_by="llm",
                citations=citations_out,
            )
