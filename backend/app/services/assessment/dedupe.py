"""Question fingerprinting and deduplication (lexical and semantic)."""

import hashlib
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.assessment import Assessment, Question
from app.services.assessment.schemas import CandidateQuestion
from app.services.llm import get_llm_client
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def compute_prompt_fingerprint(prompt: str) -> str:
    """Compute sha256 fingerprint from normalized prompt text.

    Normalization: lowercase, strip all punctuation except letters/numbers, collapse whitespace.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", prompt.lower())
    collapsed = " ".join(cleaned.split()).strip()
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()


def get_student_past_fingerprints(
    db: Session,
    course_id: int,
    student_id: int,
) -> Set[str]:
    """Retrieve all prompt fingerprints previously assigned to this student in this course."""
    past_fps = set(
        db.scalars(
            select(Question.fingerprint)
            .join(Assessment, Assessment.id == Question.assessment_id)
            .where(
                Assessment.course_id == course_id,
                Assessment.student_id == student_id,
            )
        ).all()
    )
    return past_fps


def deduplicate_candidates(
    db: Session,
    course_id: int,
    student_id: int,
    candidates: List[CandidateQuestion],
) -> Tuple[List[CandidateQuestion], List[Dict[str, str]], int]:
    """Filter out duplicate questions using lexical fingerprinting and vector semantic similarity.

    Returns:
        (unique_candidates, duplicates_dropped_info, total_dropped_count)
    """
    settings = get_settings()
    llm = get_llm_client()
    vstore = get_vector_store()

    past_fingerprints = get_student_past_fingerprints(db, course_id, student_id)
    seen_fingerprints: Set[str] = set(past_fingerprints)

    unique_candidates: List[CandidateQuestion] = []
    dropped_info: List[Dict[str, str]] = []

    # 1. Lexical fingerprint filter
    lexical_passed: List[CandidateQuestion] = []
    for cq in candidates:
        fp = cq.fingerprint or compute_prompt_fingerprint(cq.prompt)
        cq.fingerprint = fp
        if fp in seen_fingerprints:
            dropped_info.append({
                "prompt": cq.prompt[:120],
                "reason": "Exact or lexical fingerprint duplicate of prior question",
            })
            continue
        seen_fingerprints.add(fp)
        lexical_passed.append(cq)

    if not lexical_passed:
        return [], dropped_info, len(dropped_info)

    # 2. Semantic vector deduplication against previous questions in VectorStore
    prompts = [cq.prompt for cq in lexical_passed]
    try:
        embeddings = llm.embed_texts(prompts, task="document")
    except Exception as exc:
        logger.warning("Could not compute embeddings for semantic deduplication: %s", exc)
        embeddings = []

    semantic_passed: List[CandidateQuestion] = []
    passed_embeddings: List[List[float]] = []

    for idx, cq in enumerate(lexical_passed):
        emb = embeddings[idx] if idx < len(embeddings) else None
        is_dup = False

        if emb is not None:
            # Query VectorStore for this student's questions in this course
            similar_stored = vstore.query_similar_questions(
                course_id=course_id,
                embedding=emb,
                top_k=5,
                student_id=student_id,
            )
            for sim in similar_stored:
                if sim["score"] >= settings.quiz_dup_similarity:
                    is_dup = True
                    dropped_info.append({
                        "prompt": cq.prompt[:120],
                        "reason": f"Semantic duplicate of stored question (similarity {sim['score']:.3f} >= {settings.quiz_dup_similarity})",
                    })
                    break

            if is_dup:
                continue

            # Compare against already passed candidates in the current batch
            for past_emb in passed_embeddings:
                norm_a = np.linalg.norm(emb)
                norm_b = np.linalg.norm(past_emb)
                if norm_a > 0 and norm_b > 0:
                    sim_score = float(np.dot(emb, past_emb) / (norm_a * norm_b))
                    if sim_score >= settings.quiz_dup_similarity:
                        is_dup = True
                        dropped_info.append({
                            "prompt": cq.prompt[:120],
                            "reason": f"Semantic duplicate of intra-batch question (similarity {sim_score:.3f} >= {settings.quiz_dup_similarity})",
                        })
                        break

        if not is_dup:
            semantic_passed.append(cq)
            if emb is not None:
                passed_embeddings.append(emb)

    return semantic_passed, dropped_info, len(dropped_info)
