from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source import Chunk, Source
from app.models.topic import ChunkTopic
from app.services.llm import get_llm_client
from app.services.vector_store import get_vector_store


@dataclass
class RetrievedChunk:
    """Wrapper holding a retrieved chunk, its parent source, and its similarity score."""

    chunk: Chunk
    source: Source
    score: float


def retrieve(
    db: Session,
    course_id: int,
    query: str,
    top_k: int = 6,
    topic_ids: Optional[List[int]] = None,
) -> List[RetrievedChunk]:
    """Retrieve top-k relevant chunks for a course query, optionally constrained by topics."""
    llm = get_llm_client()
    vstore = get_vector_store()

    # If topic filtering requested, find all chunk_ids associated with those topics
    chunk_id_filter: Optional[List[int]] = None
    if topic_ids:
        chunk_ids = list(
            db.scalars(
                select(ChunkTopic.chunk_id)
                .where(ChunkTopic.topic_id.in_(topic_ids))
                .distinct()
            ).all()
        )
        if not chunk_ids:
            return []
        chunk_id_filter = chunk_ids

    # Compute query embedding
    query_embeddings = llm.embed_texts([query], task="query")
    if not query_embeddings:
        return []
    query_emb = query_embeddings[0]

    hits = vstore.query_chunks(
        course_id=course_id,
        query_embedding=query_emb,
        top_k=top_k,
        chunk_ids=chunk_id_filter,
    )

    results: List[RetrievedChunk] = []
    for hit in hits:
        chunk_obj = db.get(Chunk, hit["chunk_id"])
        if not chunk_obj or chunk_obj.course_id != course_id:
            continue
        source_obj = db.get(Source, chunk_obj.source_id)
        if not source_obj:
            continue
        results.append(
            RetrievedChunk(
                chunk=chunk_obj,
                source=source_obj,
                score=hit["score"],
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results
