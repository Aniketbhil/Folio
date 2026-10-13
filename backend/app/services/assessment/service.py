"""Assessment orchestration service managing question generation, verification, deduplication, and persistence."""

import concurrent.futures
import logging
import random
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.assessment import Assessment, Attempt, Question
from app.models.source import Chunk, Source
from app.models.topic import Concept, Topic
from app.schemas.assessment import (
    AssessmentOut,
    QuestionAttemptOut,
    QuestionConceptOut,
    QuestionOptionOut,
    QuestionOut,
    QuestionSourceOut,
    QuestionTopicOut,
)
from app.services.assessment.dedupe import (
    compute_prompt_fingerprint,
    deduplicate_candidates,
)
from app.services.assessment.generator import (
    LiveQuestionGenerator,
    MockQuestionGenerator,
)
from app.services.assessment.schemas import CandidateQuestion
from app.services.assessment.selection import (
    TopicContext,
    allocate_questions_across_topics,
    prepare_topic_contexts,
    resolve_assessment_scope,
)
from app.services.assessment.verifier import (
    LiveQuestionVerifier,
    MockQuestionVerifier,
)
from app.services.citations import build_citation
from app.services.llm import get_llm_client
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

# Global registry of locks per (student_id, course_id) for concurrent creation safety
_STUDENT_COURSE_LOCKS: Dict[Tuple[int, int], threading.Lock] = {}
_LOCK_REGISTRY_LOCK = threading.Lock()


def _get_student_course_lock(student_id: int, course_id: int) -> threading.Lock:
    """Retrieve or create a reentrant lock for a specific (student, course) pair."""
    key = (student_id, course_id)
    with _LOCK_REGISTRY_LOCK:
        if key not in _STUDENT_COURSE_LOCKS:
            _STUDENT_COURSE_LOCKS[key] = threading.Lock()
        return _STUDENT_COURSE_LOCKS[key]


class AssessmentService:
    """Service orchestrating assessment creation and lifecycle."""

    def __init__(self) -> None:
        self.lock = threading.Lock()

    def create(
        self,
        db: Session,
        course_id: int,
        student_id: int,
        kind: str = "quiz",
        topic_ids: Optional[List[int]] = None,
        num_questions: Optional[int] = None,
        difficulty: str = "auto",
        question_types: Optional[List[str]] = None,
        title: Optional[str] = None,
    ) -> AssessmentOut:
        """Create a fully verified, deduplicated assessment and persist questions."""
        settings = get_settings()
        llm = get_llm_client()
        vstore = get_vector_store()

        # 1. Resolve scope and validation
        eligible_topics, target_count, warnings, qtypes = resolve_assessment_scope(
            db=db,
            course_id=course_id,
            student_id=student_id,
            kind=kind,
            raw_topic_ids=topic_ids,
            num_questions=num_questions,
            difficulty=difficulty,
            question_types=question_types,
        )

        # 2. Plan topic allocation
        allocation = allocate_questions_across_topics(
            db=db,
            student_id=student_id,
            topics=eligible_topics,
            target_count=target_count,
            kind=kind,
        )

        # 3. Prepare topic contexts (data loaded on main thread)
        contexts = prepare_topic_contexts(
            db=db,
            course_id=course_id,
            student_id=student_id,
            topics=eligible_topics,
            allocation=allocation,
            difficulty=difficulty,
            question_types=qtypes,
            kind=kind,
            warnings=warnings,
        )

        # Fetch all course concepts for mock distractors
        all_concepts = list(
            db.scalars(
                select(Concept.name)
                .join(Topic, Topic.id == Concept.topic_id)
                .where(Topic.course_id == course_id)
            ).all()
        )

        # Prepare generator and verifier
        if settings.llm_mock:
            generator = MockQuestionGenerator(all_concepts)
            verifier = MockQuestionVerifier()
        else:
            generator = LiveQuestionGenerator(llm)
            verifier = LiveQuestionVerifier(llm)

        # Fetch past prompts for do_not_repeat lists
        past_prompts_map: Dict[int, List[str]] = {}
        for ctx in contexts:
            past_prompts = list(
                db.scalars(
                    select(Question.prompt)
                    .where(
                        Question.course_id == course_id,
                        Question.topic_id == ctx.topic.id,
                    )
                    .order_by(Question.id.desc())
                    .limit(15)
                ).all()
            )
            past_prompts_map[ctx.topic.id] = past_prompts

        # 4. Multi-round Generation and Verification
        total_requested = target_count
        total_generated = 0
        total_verified = 0
        total_duplicates_dropped = 0
        rejected_reasons: List[Dict[str, str]] = []
        rounds_executed = 0

        verified_candidates_by_topic: Dict[int, List[CandidateQuestion]] = {
            ctx.topic.id: [] for ctx in contexts
        }

        # Build chunk lookup map for verifier
        all_chunks_map: Dict[int, Chunk] = {
            c.id: c for ctx in contexts for c in ctx.chunks
        }

        max_rounds = settings.quiz_max_rounds
        current_contexts = list(contexts)

        for current_round in range(1, max_rounds + 1):
            rounds_executed += 1
            # Parallel generation across topics
            topic_candidates: Dict[int, List[CandidateQuestion]] = {}

            if settings.llm_mock:
                # Synchronous mock generation
                for ctx in current_contexts:
                    no_repeat = past_prompts_map.get(ctx.topic.id, [])
                    cands = generator.generate_for_topic(ctx, no_repeat, seed=42 + current_round)
                    topic_candidates[ctx.topic.id] = cands
            else:
                # Concurrent live LLM calls
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=settings.quiz_parallelism
                ) as executor:
                    future_to_tid = {
                        executor.submit(
                            generator.generate_for_topic,
                            ctx,
                            past_prompts_map.get(ctx.topic.id, []),
                            42 + current_round,
                        ): ctx.topic.id
                        for ctx in current_contexts
                    }
                    for future in concurrent.futures.as_completed(future_to_tid):
                        tid = future_to_tid[future]
                        try:
                            topic_candidates[tid] = future.result()
                        except Exception as exc:
                            logger.warning("Generation thread failed for topic %d: %s", tid, exc)
                            topic_candidates[tid] = []

            # Verification per topic
            for ctx in current_contexts:
                cands = topic_candidates.get(ctx.topic.id, [])
                total_generated += len(cands)
                if not cands:
                    continue

                v_passed, v_rejected = verifier.verify_candidates(cands, all_chunks_map)
                rejected_reasons.extend(v_rejected)
                total_verified += len(v_passed)
                verified_candidates_by_topic[ctx.topic.id].extend(v_passed)

                # Add rejected prompts to no_repeat list for future rounds
                for r in v_rejected:
                    past_prompts_map.setdefault(ctx.topic.id, []).append(r["prompt"])

            # Check if all topics reached their target count
            shortfall_contexts: List[TopicContext] = []
            for ctx in contexts:
                achieved = len(verified_candidates_by_topic[ctx.topic.id])
                shortfall = ctx.requested_count - achieved
                if shortfall > 0:
                    # Create shortfall context asking for extra questions to absorb rejections
                    shortfall_ctx = TopicContext(
                        topic=ctx.topic,
                        parent_topic=ctx.parent_topic,
                        concepts=ctx.concepts,
                        chunks=ctx.chunks,
                        source_map=ctx.source_map,
                        chunk_citations=ctx.chunk_citations,
                        requested_count=shortfall * 2,
                        assigned_qtypes=ctx.assigned_qtypes,
                        assigned_difficulties=ctx.assigned_difficulties,
                        has_numerical_support=ctx.has_numerical_support,
                    )
                    shortfall_contexts.append(shortfall_ctx)

            if not shortfall_contexts:
                break
            current_contexts = shortfall_contexts

        # 5. Acquire student-course lock for Deduplication and Persistence
        student_course_lock = _get_student_course_lock(student_id, course_id)
        with student_course_lock:
            # Flatten candidates across topics up to requested counts
            all_verified_candidates: List[CandidateQuestion] = []
            for ctx in contexts:
                topic_verified = verified_candidates_by_topic[ctx.topic.id]
                all_verified_candidates.extend(topic_verified[: ctx.requested_count])

            # Deduplication
            final_candidates, dropped_dups, dup_count = deduplicate_candidates(
                db=db,
                course_id=course_id,
                student_id=student_id,
                candidates=all_verified_candidates,
            )
            total_duplicates_dropped += dup_count

            # If shortfall remains, trim or warn
            if len(final_candidates) < target_count:
                if len(final_candidates) == 0:
                    raise AppError(
                        "Could not generate any verified questions for this assessment.",
                        code="generation_failed",
                        status_code=422,
                    )
                shortfall_diff = target_count - len(final_candidates)
                warnings.append(
                    f"Generated {len(final_candidates)} question(s) instead of requested {target_count} due to strict source grounding and deduplication."
                )

            # Limit to exactly target_count if extra
            final_candidates = final_candidates[:target_count]

            # 6. Shuffle topic order deterministically per assessment
            rng = random.Random(f"{course_id}_{student_id}_{target_count}_{len(final_candidates)}")
            rng.shuffle(final_candidates)

            # 7. Persistence
            final_title = title.strip() if title and title.strip() else f"{kind.replace('_', ' ').title()} - {len(final_candidates)} Questions"

            generation_report = {
                "requested": total_requested,
                "generated": total_generated,
                "verified": total_verified,
                "rejected_reasons": rejected_reasons[:20],
                "duplicates_dropped": total_duplicates_dropped,
                "rounds": rounds_executed,
                "verify_model": settings.verify_model if settings.verify_model else None,
                "mode": "mock" if settings.llm_mock else "live",
            }

            assessment_config = {
                "kind": kind,
                "topic_ids": topic_ids,
                "num_questions": target_count,
                "difficulty": difficulty,
                "question_types": qtypes,
                "title": final_title,
                "generation_report": generation_report,
            }

            assessment = Assessment(
                course_id=course_id,
                student_id=student_id,
                kind=kind,
                status="in_progress",
                title=final_title,
                config=assessment_config,
            )
            db.add(assessment)
            db.flush()

            question_rows: List[Question] = []
            for pos, cq in enumerate(final_candidates):
                q_row = Question(
                    assessment_id=assessment.id,
                    course_id=course_id,
                    topic_id=cq.topic_id,
                    concept_id=cq.concept_id,
                    qtype=cq.qtype,
                    difficulty=cq.difficulty,
                    prompt=cq.prompt,
                    options=cq.options,
                    correct_answer=cq.correct_answer,
                    explanation=cq.explanation,
                    source_chunk_ids=cq.source_chunk_ids,
                    verified=True,
                    verification_notes=cq.verification_notes,
                    fingerprint=cq.fingerprint,
                    position=pos,
                    meta=cq.meta,
                )
                db.add(q_row)
                question_rows.append(q_row)

            db.commit()
            db.refresh(assessment)
            for qr in question_rows:
                db.refresh(qr)

        # 8. Insert into vector store (outside DB transaction)
        try:
            vector_items = []
            prompts = [qr.prompt for qr in question_rows]
            embeddings = llm.embed_texts(prompts, task="document")
            for qr, emb in zip(question_rows, embeddings):
                vector_items.append({
                    "question_id": qr.id,
                    "course_id": qr.course_id,
                    "student_id": assessment.student_id,
                    "assessment_id": assessment.id,
                    "topic_id": qr.topic_id,
                    "prompt": qr.prompt,
                    "embedding": emb,
                })
            vstore.add_questions(vector_items)
        except Exception as exc:
            logger.warning(
                "Could not insert questions into Chroma vector store for assessment %d: %s",
                assessment.id,
                exc,
            )

        # 9. Format response (masking sensitive fields)
        return self._format_assessment_out(
            db=db,
            assessment=assessment,
            question_rows=question_rows,
            warnings=warnings,
            generation_report=generation_report,
        )

    def _format_assessment_out(
        self,
        db: Session,
        assessment: Assessment,
        question_rows: List[Question],
        warnings: List[str],
        generation_report: Dict[str, Any],
    ) -> AssessmentOut:
        """Format public AssessmentOut response without revealing keys or rubric for in-progress tests."""
        # Load topic and concept details
        topic_ids = {qr.topic_id for qr in question_rows}
        concept_ids = {qr.concept_id for qr in question_rows if qr.concept_id is not None}

        topics_map = {
            t.id: t for t in db.scalars(select(Topic).where(Topic.id.in_(topic_ids))).all()
        }
        parent_ids = {t.parent_id for t in topics_map.values() if t.parent_id is not None}
        parents_map = (
            {p.id: p for p in db.scalars(select(Topic).where(Topic.id.in_(parent_ids))).all()}
            if parent_ids
            else {}
        )
        concepts_map = (
            {c.id: c for c in db.scalars(select(Concept).where(Concept.id.in_(concept_ids))).all()}
            if concept_ids
            else {}
        )

        all_chunk_ids = {cid for qr in question_rows for cid in qr.source_chunk_ids}
        chunks_map = (
            {c.id: c for c in db.scalars(select(Chunk).where(Chunk.id.in_(all_chunk_ids))).all()}
            if all_chunk_ids
            else {}
        )
        source_ids = {c.source_id for c in chunks_map.values()}
        sources_map = (
            {s.id: s for s in db.scalars(select(Source).where(Source.id.in_(source_ids))).all()}
            if source_ids
            else {}
        )

        out_questions: List[QuestionOut] = []
        is_submitted = assessment.status == "submitted"

        # Query attempts for this assessment to populate answered status and attempt details
        attempts_map = {
            att.question_id: att
            for att in db.scalars(
                select(Attempt).where(Attempt.assessment_id == assessment.id)
            ).all()
        }

        for qr in question_rows:
            top = topics_map.get(qr.topic_id)
            ptop = parents_map.get(top.parent_id) if top and top.parent_id else None
            conc = concepts_map.get(qr.concept_id) if qr.concept_id else None

            # Format options
            opts_out: Optional[List[QuestionOptionOut]] = None
            if qr.options:
                opts_out = [
                    QuestionOptionOut(key=o["key"], text=o["text"]) for o in qr.options
                ]

            # Format sources
            srcs_out: List[QuestionSourceOut] = []
            for cid in qr.source_chunk_ids:
                chk = chunks_map.get(cid)
                if chk:
                    src_obj = sources_map.get(chk.source_id)
                    src_title = src_obj.title if src_obj else "Source"
                    cit = build_citation(chk, src_obj) if src_obj else None
                    loc = cit.location if cit else {}
                    srcs_out.append(
                        QuestionSourceOut(
                            chunk_id=chk.id,
                            source_id=chk.source_id,
                            source_title=src_title,
                            source_type=chk.source_type,
                            location=loc,
                        )
                    )

            unit_label = qr.meta.get("unit") if qr.meta else None

            att = attempts_map.get(qr.id)
            is_answered = att is not None
            reveal_keys = is_submitted or is_answered

            attempt_out = None
            if att:
                attempt_out = QuestionAttemptOut(
                    answer=att.answer,
                    is_correct=att.is_correct,
                    score=att.score,
                    feedback=att.feedback,
                )

            out_questions.append(
                QuestionOut(
                    id=qr.id,
                    position=qr.position,
                    qtype=qr.qtype,
                    difficulty=qr.difficulty,
                    prompt=qr.prompt,
                    options=opts_out,
                    topic=QuestionTopicOut(
                        id=top.id if top else qr.topic_id,
                        name=top.name if top else "Topic",
                        parent_id=ptop.id if ptop else None,
                        parent_name=ptop.name if ptop else None,
                    ),
                    concept=QuestionConceptOut(id=conc.id, name=conc.name) if conc else None,
                    sources=srcs_out,
                    answered=is_answered,
                    unit=unit_label,
                    attempt=attempt_out,
                    correct_answer=qr.correct_answer if reveal_keys else None,
                    explanation=qr.explanation if reveal_keys else None,
                )
            )

        return AssessmentOut(
            id=assessment.id,
            course_id=assessment.course_id,
            student_id=assessment.student_id,
            kind=assessment.kind,
            status=assessment.status,
            title=assessment.title,
            config=assessment.config or {},
            num_questions=len(out_questions),
            answered_count=len(attempts_map),
            score=assessment.score,
            created_at=assessment.created_at,
            warnings=warnings,
            generation_report=generation_report,
            questions=out_questions,
        )


_assessment_service = AssessmentService()


def get_assessment_service() -> AssessmentService:
    """Singleton getter for AssessmentService."""
    return _assessment_service
