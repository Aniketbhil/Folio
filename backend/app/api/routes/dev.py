from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.source import Chunk, Source
from app.schemas.citation import Citation
from app.schemas.tutor import DevAskRequest, DevAskResponse
from app.schemas.dev import (
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
        topic_ids=payload.topic_ids,
        history=payload.history,
    )

