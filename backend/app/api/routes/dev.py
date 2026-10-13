from datetime import timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.mastery import Mastery
from app.models.source import Chunk, Source
from app.models.topic import Topic
from app.schemas.citation import Citation
from app.schemas.learner import (
    DevAgeMasteryRequest,
    DevAgeMasteryResponse,
    DevForgettingSimulateItem,
    DevForgettingSimulateRequest,
)
from app.schemas.tutor import DevAskRequest, DevAskResponse
from app.schemas.assessment import (
    DevBktSimulateRequest,
    DevBktSimulateResponse,
    DevBktTrajectoryItem,
    DevGenerateQuestionsRequest,
    DevGenerateQuestionsResponse,
)
from app.services.learner.forgetting import retrievability
from app.services.learner.mastery import bkt_update
from app.schemas.dev import (
    DevIntegrityDetails,
    DevIntegrityResponse,
    EmbedTestRequest,
    EmbedTestResponse,
    LLMTestRequest,
    LLMTestResponse,
    VectorTestResultItem,
    VectorTestResponse,
)
from app.services.citations import build_citation
from app.services.llm import LLMClient, get_llm_client
from app.services.retrieval import retrieve
from app.services.tutor import get_tutor_service
from app.services.vector_store import VectorStore, get_vector_store

router = APIRouter(prefix="/dev", tags=["Developer"])


@router.post("/llm-test", response_model=LLMTestResponse)
def test_llm(
    payload: LLMTestRequest,
    llm: LLMClient = Depends(get_llm_client),
) -> LLMTestResponse:
    """Test LLM generation in current mode (mock or live)."""
    settings = get_settings()
    mode = "mock" if settings.llm_mock else "live"
    output = llm.generate_text(payload.prompt)
    return LLMTestResponse(mode=mode, output=output)


@router.post("/embed-test", response_model=EmbedTestResponse)
def test_embed(
    payload: EmbedTestRequest,
    llm: LLMClient = Depends(get_llm_client),
) -> EmbedTestResponse:
    """Test embedding generation dimensions and count."""
    embeddings = llm.embed_texts(payload.texts, task="document")
    dim = len(embeddings[0]) if embeddings else 0
    return EmbedTestResponse(dim=dim, count=len(embeddings))


@router.post("/vector-test", response_model=VectorTestResponse)
def test_vector(
    llm: LLMClient = Depends(get_llm_client),
    vector_store: VectorStore = Depends(get_vector_store),
) -> VectorTestResponse:
    """Insert 3 test chunks under temp course 0, run query, verify, and clean up."""
    temp_course_id = 0
    docs = [
        "Photosynthesis is the process by which green plants convert light into chemical energy.",
        "Cellular respiration produces ATP by breaking down glucose.",
        "Newton's second law states that Force equals mass times acceleration.",
    ]
    doc_embeddings = llm.embed_texts(docs, task="document")

    fake_chunks = [
        {
            "chunk_id": 99901,
            "course_id": temp_course_id,
            "source_id": 999,
            "text": docs[0],
            "embedding": doc_embeddings[0],
            "topic_id": 1,
        },
        {
            "chunk_id": 99902,
            "course_id": temp_course_id,
            "source_id": 999,
            "text": docs[1],
            "embedding": doc_embeddings[1],
            "topic_id": 1,
        },
        {
            "chunk_id": 99903,
            "course_id": temp_course_id,
            "source_id": 999,
            "text": docs[2],
            "embedding": doc_embeddings[2],
            "topic_id": 2,
        },
    ]

    vector_store.add_chunks(fake_chunks)

    query_text = "How do green plants capture light energy?"
    query_emb = llm.embed_texts([query_text], task="query")[0]
    query_results = vector_store.query_chunks(
        course_id=temp_course_id, query_embedding=query_emb, top_k=3
    )

    # Clean up temporary test data
    vector_store.delete_by_course(temp_course_id)

    return VectorTestResponse(
        success=True,
        queried_chunks=[
            VectorTestResultItem(
                chunk_id=res["chunk_id"],
                score=res["score"],
                distance=res["distance"],
            )
            for res in query_results
        ],
        cleaned_up=True,
    )


@router.get("/search", response_model=List[Citation])
def dev_search(
    course_id: int,
    q: str,
    top_k: int = 6,
    db: Session = Depends(get_db),
) -> List[Citation]:
    """Perform hybrid retrieval against vector store and relational metadata."""
    settings = get_settings()
    if not settings.debug:
        raise AppError(
            "Dev endpoints are only available in debug mode",
            code="forbidden",
            status_code=403,
        )
    retrieved = retrieve(db=db, course_id=course_id, query=q, top_k=top_k)
    return [build_citation(rc.chunk, rc.source, score=rc.score) for rc in retrieved]


@router.post("/vector-reset")
def dev_vector_reset(
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Drop and recreate both Chroma collections, and reset chunk embedded flags."""
    settings = get_settings()
    if not settings.debug:
        raise AppError(
            "Dev endpoints are only available in debug mode",
            code="forbidden",
            status_code=403,
        )
    vector_store.reset_collections()
    result = db.execute(update(Chunk).values(embedded=False))
    db.commit()
    count = result.rowcount
    return {"reset": True, "chunks_unembedded": count}


@router.post("/reembed-all")
def dev_reembed_all(
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
    vector_store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Re-run the embedding stage over all chunks across all ready sources."""
    settings = get_settings()
    if not settings.debug:
        raise AppError(
            "Dev endpoints are only available in debug mode",
            code="forbidden",
            status_code=403,
        )

    ready_sources = list(
        db.scalars(select(Source).where(Source.status == "ready")).all()
    )

    embedded_count = 0
    failed_count = 0
    batch_size = 32

    for source in ready_sources:
        try:
            chunks = list(
                db.scalars(
                    select(Chunk)
                    .where(Chunk.source_id == source.id)
                    .order_by(Chunk.chunk_index.asc())
                ).all()
            )
            if not chunks:
                continue

            vector_store.delete_by_source(source.id)

            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                texts = [
                    ((c.section_title + "\n") if c.section_title else "") + c.text[:2000]
                    for c in batch
                ]
                embeddings = llm.embed_texts(texts, task="document")

                records = [
                    {
                        "chunk_id": c.id,
                        "course_id": c.course_id,
                        "source_id": c.source_id,
                        "text": c.text,
                        "embedding": emb,
                    }
                    for c, emb in zip(batch, embeddings)
                ]
                vector_store.add_chunks(records)

                for c in batch:
                    c.embedded = True
                db.commit()
                embedded_count += len(batch)
        except Exception:
            failed_count += 1

    return {
        "sources": len(ready_sources),
        "chunks_embedded": embedded_count,
        "chunks_failed": failed_count,
    }


@router.post("/ask", response_model=DevAskResponse)
def dev_ask(
    payload: DevAskRequest,
    db: Session = Depends(get_db),
) -> DevAskResponse:
    """Run retrieval, gate, and answer without persisting conversation or messages."""
    settings = get_settings()
    if not settings.debug:
        raise AppError(
            "Dev endpoints are only available in debug mode",
            code="forbidden",
            status_code=403,
        )
    tutor = get_tutor_service()
    return tutor.ask_dev(
        db=db,
        course_id=payload.course_id,
        question=payload.question,
        student_id=payload.student_id,
        topic_ids=payload.topic_ids,
        history=payload.history,
    )


@router.post("/generate-questions", response_model=DevGenerateQuestionsResponse)
def dev_generate_questions(
    payload: DevGenerateQuestionsRequest,
    db: Session = Depends(get_db),
) -> DevGenerateQuestionsResponse:
    """Run selection + generation + verification + dedupe WITHOUT persisting anything."""
    from app.models.course import Course
    from app.models.topic import Concept, Topic
    from app.services.assessment.selection import (
        TopicContext,
        plan_topic_difficulty_and_qtypes,
        select_topic_chunks,
    )
    from app.services.assessment.generator import (
        LiveQuestionGenerator,
        MockQuestionGenerator,
    )
    from app.services.assessment.verifier import (
        LiveQuestionVerifier,
        MockQuestionVerifier,
    )
    from app.services.assessment.dedupe import deduplicate_candidates

    settings = get_settings()
    if not settings.debug:
        raise AppError(
            "Dev endpoints are only available in debug mode",
            code="forbidden",
            status_code=403,
        )

    course = db.get(Course, payload.course_id)
    if not course:
        raise AppError(f"Course {payload.course_id} not found", code="course_not_found", status_code=404)

    topic = db.get(Topic, payload.topic_id)
    if not topic or topic.course_id != payload.course_id:
        raise AppError(f"Topic {payload.topic_id} not found in course", code="topic_not_found", status_code=404)

    student_id = payload.student_id or 0
    warnings: List[str] = []

    chunks, source_map, chunk_cits, has_num = select_topic_chunks(
        db=db,
        student_id=student_id,
        course_id=payload.course_id,
        topic_id=payload.topic_id,
    )
    if not chunks:
        raise AppError("No chunks tagged to this topic", code="no_content", status_code=404)

    parent_topic = db.get(Topic, topic.parent_id) if topic.parent_id else None
    concepts = list(db.scalars(select(Concept).where(Concept.topic_id == topic.id)).all())

    diffs, qtypes = plan_topic_difficulty_and_qtypes(
        db=db,
        student_id=student_id,
        topic=topic,
        count=payload.num_questions,
        difficulty=payload.difficulty,
        question_types=payload.question_types,
        kind="quiz",
        has_numerical=has_num,
        warnings=warnings,
    )

    ctx = TopicContext(
        topic=topic,
        parent_topic=parent_topic,
        concepts=concepts,
        chunks=chunks,
        source_map=source_map,
        chunk_citations=chunk_cits,
        requested_count=payload.num_questions,
        assigned_qtypes=qtypes,
        assigned_difficulties=diffs,
        has_numerical_support=has_num,
    )

    all_concepts = list(
        db.scalars(
            select(Concept.name)
            .join(Topic, Topic.id == Concept.topic_id)
            .where(Topic.course_id == payload.course_id)
        ).all()
    )

    llm = get_llm_client()
    if settings.llm_mock:
        gen = MockQuestionGenerator(all_concepts)
        ver = MockQuestionVerifier()
    else:
        gen = LiveQuestionGenerator(llm)
        ver = LiveQuestionVerifier(llm)

    cands = gen.generate_for_topic(ctx, [], seed=42)
    all_chunks_map = {c.id: c for c in chunks}
    verified, rejected = ver.verify_candidates(cands, all_chunks_map)
    final_unique, duplicates, _ = deduplicate_candidates(db, payload.course_id, student_id, verified)

    accepted_list = []
    for q in final_unique:
        accepted_list.append({
            "topic_id": q.topic_id,
            "concept_id": q.concept_id,
            "qtype": q.qtype,
            "difficulty": q.difficulty,
            "prompt": q.prompt,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "source_chunk_ids": q.source_chunk_ids,
            "key_points": q.meta.get("key_points") if q.meta else None,
            "tolerance_pct": q.meta.get("tolerance_pct") if q.meta else None,
            "unit": q.unit,
            "verified": q.verified,
            "verification_notes": q.verification_notes,
            "fingerprint": q.fingerprint,
        })

    return DevGenerateQuestionsResponse(
        accepted=accepted_list,
        rejected=rejected,
        duplicates=duplicates,
        mode="mock" if settings.llm_mock else "live",
        verify_model=settings.verify_model if settings.verify_model else None,
    )


@router.post("/bkt-simulate", response_model=DevBktSimulateResponse)
def simulate_bkt(payload: DevBktSimulateRequest) -> DevBktSimulateResponse:
    """Simulate BKT probability trajectory for a sequence of questions without writing to DB."""
    settings = get_settings()
    current_p = payload.p_init if payload.p_init is not None else settings.bkt_p_init
    trajectory: List[DevBktTrajectoryItem] = []

    for idx, item in enumerate(payload.sequence, start=1):
        p_before = current_p
        p_after = bkt_update(
            p_prior=p_before,
            score=item.score,
            qtype=item.qtype,
            difficulty=item.difficulty,
        )
        trajectory.append(
            DevBktTrajectoryItem(
                step=idx,
                score=item.score,
                qtype=item.qtype,
                difficulty=item.difficulty,
                p_before=p_before,
                p_after=p_after,
            )
        )
        current_p = p_after

    return DevBktSimulateResponse(trajectory=trajectory)


@router.post("/age-mastery", response_model=DevAgeMasteryResponse)
def dev_age_mastery(
    payload: DevAgeMasteryRequest,
    db: Session = Depends(get_db),
) -> DevAgeMasteryResponse:
    """Shift last_practiced_at back by N days for all student's mastery rows in the course."""
    settings = get_settings()
    if not settings.debug:
        raise AppError(
            "Dev endpoints are only available in debug mode",
            code="forbidden",
            status_code=403,
        )

    all_topics = db.scalars(select(Topic).where(Topic.course_id == payload.course_id)).all()
    parent_ids = {t.parent_id for t in all_topics if t.parent_id is not None}
    leaf_ids = [t.id for t in all_topics if t.id not in parent_ids]

    if not leaf_ids:
        return DevAgeMasteryResponse(rows_affected=0)

    rows = db.scalars(
        select(Mastery).where(
            Mastery.student_id == payload.student_id,
            Mastery.topic_id.in_(leaf_ids),
            Mastery.last_practiced_at.is_not(None),
        )
    ).all()

    for m in rows:
        m.last_practiced_at = m.last_practiced_at - timedelta(days=payload.days)

    db.commit()
    return DevAgeMasteryResponse(rows_affected=len(rows))


@router.post("/forgetting-simulate", response_model=List[DevForgettingSimulateItem])
def dev_forgetting_simulate(
    payload: DevForgettingSimulateRequest,
) -> List[DevForgettingSimulateItem]:
    """Pure simulation of retrievability and effective mastery decay across days."""
    settings = get_settings()
    results: List[DevForgettingSimulateItem] = []
    p_init = settings.bkt_p_init
    p_orig = float(payload.p_mastery)

    for d in payload.days:
        r = retrievability(float(d), payload.correct_count)
        if p_orig > p_init:
            eff = p_init + (p_orig - p_init) * r
        else:
            eff = p_orig
        results.append(
            DevForgettingSimulateItem(
                days=float(d),
                retrievability=round(r, 4),
                effective_mastery=round(eff, 4),
            )
        )
    return results


@router.get("/integrity-check", response_model=DevIntegrityResponse)
def dev_integrity_check(
    fix: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> DevIntegrityResponse:
    """Audit database and vector store for consistency issues, with optional repair."""
    settings = get_settings()
    if not settings.debug:
        raise AppError("Dev endpoints are only available in debug mode", code="forbidden", status_code=403)

    from app.models.assessment import Question
    from app.models.course import Course
    from app.models.topic import ChunkTopic, Topic
    from app.services.llm import get_llm_client

    vstore = get_vector_store()
    llm = get_llm_client()

    # 1. Orphan chunk vectors
    chroma_chunk_ids_raw = vstore.chunks_collection.get(include=[])["ids"]
    vector_chunk_ids = {int(x) for x in chroma_chunk_ids_raw if x.isdigit()}
    db_chunk_ids = set(db.scalars(select(Chunk.id)).all())
    orphan_vectors = sorted(list(vector_chunk_ids - db_chunk_ids))

    # 2. Chunks not embedded
    chunks_not_embedded = sorted(list(db.scalars(select(Chunk.id).where(Chunk.embedded == False)).all()))

    # 3. Vectors missing for embedded chunks
    db_embedded_ids = set(db.scalars(select(Chunk.id).where(Chunk.embedded == True)).all())
    vectors_missing_for_embedded = sorted(list(db_embedded_ids - vector_chunk_ids))

    # 4. Topics without chunks (leaf topics with 0 ChunkTopic rows)
    all_topics = db.scalars(select(Topic)).all()
    parent_ids = {t.parent_id for t in all_topics if t.parent_id is not None}
    leaf_topic_ids = {t.id for t in all_topics if t.id not in parent_ids}
    tagged_topic_ids = set(db.scalars(select(ChunkTopic.topic_id).distinct()).all())
    topics_without_chunks = sorted(list(leaf_topic_ids - tagged_topic_ids))

    # 5. Sources ready without chunks
    ready_sources = db.scalars(select(Source).where(Source.status == "ready")).all()
    sources_with_chunks = set(db.scalars(select(Chunk.source_id).distinct()).all())
    sources_ready_without_chunks = sorted([s.id for s in ready_sources if s.id not in sources_with_chunks])

    # 6. Questions without vectors
    chroma_q_ids_raw = vstore.questions_collection.get(include=[])["ids"]
    vector_q_ids = {int(x) for x in chroma_q_ids_raw if x.isdigit()}
    db_q_ids = set(db.scalars(select(Question.id)).all())
    questions_without_vectors = sorted(list(db_q_ids - vector_q_ids))

    # 7. Stuck sources
    stuck_sources = sorted(list(db.scalars(select(Source.id).where(Source.status.in_(["queued", "processing"]))).all()))

    # 8. Stuck courses
    stuck_courses = sorted(list(db.scalars(select(Course.id).where(Course.kb_status == "building")).all()))

    issues = DevIntegrityDetails(
        orphan_vectors=orphan_vectors,
        chunks_not_embedded=chunks_not_embedded,
        vectors_missing_for_embedded_chunks=vectors_missing_for_embedded,
        topics_without_chunks=topics_without_chunks,
        sources_ready_without_chunks=sources_ready_without_chunks,
        questions_without_vectors=questions_without_vectors,
        stuck_sources=stuck_sources,
        stuck_courses=stuck_courses,
    )

    clean = not any([
        orphan_vectors,
        chunks_not_embedded,
        vectors_missing_for_embedded,
        topics_without_chunks,
        sources_ready_without_chunks,
        questions_without_vectors,
        stuck_sources,
        stuck_courses,
    ])

    fixed_info = None
    if fix:
        fixed_info = {}
        # Delete orphan vectors
        if orphan_vectors:
            vstore.chunks_collection.delete(ids=[str(x) for x in orphan_vectors])
            fixed_info["orphan_vectors_deleted"] = len(orphan_vectors)

        # Re-embed missing chunks
        to_reembed_ids = set(chunks_not_embedded + vectors_missing_for_embedded)
        if to_reembed_ids:
            reembed_chunks = list(db.scalars(select(Chunk).where(Chunk.id.in_(to_reembed_ids))).all())
            if reembed_chunks:
                texts = [(((c.section_title + "\n") if c.section_title else "") + c.text)[:2000] for c in reembed_chunks]
                embeddings = llm.embed_texts(texts, task="document")
                vstore.add_chunks([
                    {
                        "chunk_id": c.id,
                        "course_id": c.course_id,
                        "source_id": c.source_id,
                        "text": c.text,
                        "embedding": emb,
                    }
                    for c, emb in zip(reembed_chunks, embeddings)
                ])
                for c in reembed_chunks:
                    c.embedded = True
                db.commit()
                fixed_info["chunks_reembedded"] = len(reembed_chunks)

        # Re-add missing question vectors
        if questions_without_vectors:
            reembed_qs = list(db.scalars(select(Question).where(Question.id.in_(questions_without_vectors))).all())
            if reembed_qs:
                q_texts = [q.prompt for q in reembed_qs]
                q_embs = llm.embed_texts(q_texts, task="document")
                vstore.add_questions([
                    {
                        "question_id": q.id,
                        "course_id": q.course_id,
                        "topic_id": q.topic_id,
                        "text": q.prompt,
                        "embedding": emb,
                        "student_id": q.assessment.student_id if q.assessment else None,
                    }
                    for q, emb in zip(reembed_qs, q_embs)
                ])
                fixed_info["questions_reembedded"] = len(reembed_qs)

        # Mark stuck sources failed
        if stuck_sources:
            for s in db.scalars(select(Source).where(Source.id.in_(stuck_sources))).all():
                s.status = "failed"
                s.error = "Integrity check marked as failed"
            db.commit()
            fixed_info["stuck_sources_failed"] = len(stuck_sources)

        # Mark stuck courses failed
        if stuck_courses:
            for c in db.scalars(select(Course).where(Course.id.in_(stuck_courses))).all():
                c.kb_status = "failed"
                c.kb_error = "Integrity check marked as failed"
            db.commit()
            fixed_info["stuck_courses_failed"] = len(stuck_courses)

    return DevIntegrityResponse(
        clean=clean,
        issues=issues,
        fixed=fixed_info,
    )


