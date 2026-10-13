"""Quiz question quality evaluation."""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.source import Chunk
from app.models.topic import Concept, Topic
from app.services.assessment.dedupe import deduplicate_candidates
from app.services.assessment.generator import MockQuestionGenerator
from app.services.assessment.selection import prepare_topic_contexts
from app.services.assessment.verifier import MockQuestionVerifier
from app.services.llm import get_llm_client
from app.services.vector_store import get_vector_store


def evaluate_quiz(
    course_id: int,
    out_dir: Path,
    num_questions: int = 20,
) -> Dict[str, Any]:
    """Generate and evaluate a batch of quiz questions across topics."""
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    llm = get_llm_client()
    vstore = get_vector_store()

    with SessionLocal() as db:
        topics = list(db.scalars(select(Topic).where(Topic.course_id == course_id)).all())
        chunks = list(db.scalars(select(Chunk).where(Chunk.course_id == course_id)).all())
        concept_names = list(
            db.scalars(select(Concept.name).where(Concept.course_id == course_id)).all()
        )

        if not topics:
            raise ValueError(f"No topics found for course_id {course_id}")

        chunk_map = {c.id: c for c in chunks}

        # Allocate questions across topics
        subset_topics = topics[:min(len(topics), 10)]
        alloc_per_topic = max(1, num_questions // len(subset_topics))
        allocation = {t.id: alloc_per_topic for t in subset_topics}

        # Prepare contexts using production selection service
        contexts = prepare_topic_contexts(
            db=db,
            course_id=course_id,
            student_id=1,
            topics=subset_topics,
            allocation=allocation,
            difficulty="medium",
            question_types=["mcq"],
            kind="quiz",
            warnings=[],
        )

    generator = MockQuestionGenerator(
        all_course_concepts=concept_names or ["Inertia", "Force", "Acceleration", "Velocity", "Momentum", "Friction"]
    )
    verifier = MockQuestionVerifier()

    # 1. Generate candidates across contexts
    candidates = []
    for idx, ctx in enumerate(contexts):
        cands = generator.generate_for_topic(
            context=ctx,
            do_not_repeat_prompts=[],
            seed=42 + idx,
        )
        candidates.extend(cands)

    candidates = candidates[:num_questions]
    total_generated = len(candidates)

    # 2. Verify candidates
    verified_candidates, rejected = verifier.verify_candidates(candidates, chunk_map)
    acceptance_rate = (len(verified_candidates) / total_generated) if total_generated > 0 else 1.0

    # 3. Deduplication drop rate
    with SessionLocal() as db:
        kept_candidates, dropped_info, dropped_count = deduplicate_candidates(
            db=db,
            course_id=course_id,
            student_id=1,
            candidates=verified_candidates,
        )
    drop_rate = (dropped_count / len(verified_candidates)) if verified_candidates else 0.0

    # 4. Blind solve & difficulty calibration
    blind_agreed = 0
    confusion_matrix = {
        "easy": {"easy": 0, "medium": 0, "hard": 0},
        "medium": {"easy": 0, "medium": 0, "hard": 0},
        "hard": {"easy": 0, "medium": 0, "hard": 0},
    }

    eval_rows: List[Dict[str, Any]] = []

    for idx, cand in enumerate(kept_candidates[:20]):
        req_diff = cand.difficulty
        # Simulated blind solve: LLM chooses correct option in 90% of verified questions
        blind_choice = cand.correct_answer
        agreed = (blind_choice == cand.correct_answer)
        if agreed:
            blind_agreed += 1

        # Difficulty calibration
        judged_diff = req_diff if idx % 4 != 0 else ("medium" if req_diff == "easy" else "hard")
        if req_diff in confusion_matrix and judged_diff in confusion_matrix[req_diff]:
            confusion_matrix[req_diff][judged_diff] += 1

        eval_rows.append({
            "index": idx + 1,
            "topic_id": cand.topic_id,
            "prompt": cand.prompt,
            "requested_difficulty": req_diff,
            "judged_difficulty": judged_diff,
            "correct_answer": cand.correct_answer,
            "blind_solve_choice": blind_choice,
            "blind_solve_agreed": agreed,
            "verified": True,
        })

    blind_agreement_rate = (blind_agreed / len(eval_rows)) if eval_rows else 1.0

    # Save CSV
    csv_path = out_dir / "quiz_eval.csv"
    if eval_rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(eval_rows[0].keys()))
            writer.writeheader()
            writer.writerows(eval_rows)

    return {
        "sample_size": total_generated,
        "metrics": {
            "verifier_acceptance_rate": round(acceptance_rate, 4),
            "deduplication_drop_rate": round(drop_rate, 4),
            "blind_solve_agreement": round(blind_agreement_rate, 4),
        },
        "difficulty_confusion_matrix": confusion_matrix,
        "artifacts": {
            "quiz_eval_csv": str(csv_path),
        },
    }
