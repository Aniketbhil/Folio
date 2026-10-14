from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.source import Chunk, Source
from app.models.topic import ChunkConcept, ChunkTopic, Concept, Topic
from app.schemas.chunk import (
    ChunkConceptBrief,
    ChunkDetail,
    ChunkNeighbor,
    ChunkSourceDetail,
    ChunkTopicBrief,
    ChunkViewer,
    ChunkViewerResponse,
)
from app.services.auth.dependencies import get_current_student

router = APIRouter(prefix="/chunks", tags=["chunks"], dependencies=[Depends(get_current_student)])


def _get_location(c: Chunk) -> Dict[str, Any]:
    if c.source_type == "pdf":
        return {"page": c.page_number}
    elif c.source_type == "slide":
        return {"slide": c.slide_number}
    elif c.source_type in ("video", "video_transcript"):
        return {"start_sec": c.start_sec, "end_sec": c.end_sec}
    return {}


def _build_seek_url(media_url: Optional[str], start_sec: Optional[float]) -> Optional[str]:
    if not media_url:
        return None
    if start_sec is None:
        return media_url
    if "youtube.com" in media_url or "youtu.be" in media_url:
        sep = "&" if "?" in media_url else "?"
        return f"{media_url}{sep}t={int(start_sec)}s"
    return media_url


@router.get("/{chunk_id}", response_model=ChunkViewerResponse)
def get_chunk_viewer(
    chunk_id: int,
    db: Session = Depends(get_db),
) -> ChunkViewerResponse:
    """Retrieve detailed chunk information for citation viewing and navigation."""
    chunk = db.get(Chunk, chunk_id)
    if not chunk:
        raise AppError(
            f"Chunk with id {chunk_id} not found",
            code="chunk_not_found",
            status_code=404,
        )

    source = db.get(Source, chunk.source_id)
    if not source:
        raise AppError(
            f"Source with id {chunk.source_id} not found",
            code="source_not_found",
            status_code=404,
        )

    media_url: Optional[str] = (
        source.meta.get("media_url")
        if (source.meta and isinstance(source.meta, dict))
        else None
    )
    seek_url = _build_seek_url(media_url, chunk.start_sec)

    st = (chunk.source_type or "").lower()
    if st == "pdf":
        viewer = ChunkViewer(
            kind="pdf_page",
            page=chunk.page_number,
            slide=None,
            start_sec=None,
            end_sec=None,
            has_timestamps=False,
        )
    elif st == "slide":
        viewer = ChunkViewer(
            kind="slide",
            page=None,
            slide=chunk.slide_number,
            start_sec=None,
            end_sec=None,
            has_timestamps=False,
        )
    elif st in ("video", "video_transcript"):
        has_time = chunk.start_sec is not None
        viewer = ChunkViewer(
            kind="video_time" if has_time else "text",
            page=None,
            slide=None,
            start_sec=chunk.start_sec,
            end_sec=chunk.end_sec,
            has_timestamps=has_time,
        )
    else:
        viewer = ChunkViewer(
            kind="text",
            page=None,
            slide=None,
            start_sec=None,
            end_sec=None,
            has_timestamps=False,
        )

    # Neighbors in the same source by chunk_index
    prev_chunk = db.scalar(
        select(Chunk).where(
            Chunk.source_id == chunk.source_id,
            Chunk.chunk_index == chunk.chunk_index - 1,
        )
    )
    previous = (
        ChunkNeighbor(
            id=prev_chunk.id,
            location=_get_location(prev_chunk),
            preview=prev_chunk.text[:120],
        )
        if prev_chunk
        else None
    )

    next_chunk = db.scalar(
        select(Chunk).where(
            Chunk.source_id == chunk.source_id,
            Chunk.chunk_index == chunk.chunk_index + 1,
        )
    )
    next_val = (
        ChunkNeighbor(
            id=next_chunk.id,
            location=_get_location(next_chunk),
            preview=next_chunk.text[:120],
        )
        if next_chunk
        else None
    )

    # Topics associated with chunk
    topic_rows = db.execute(
        select(Topic.id, Topic.name, ChunkTopic.relevance)
        .join(ChunkTopic, ChunkTopic.topic_id == Topic.id)
        .where(ChunkTopic.chunk_id == chunk.id)
        .order_by(ChunkTopic.relevance.desc())
    ).all()
    topics = [
        ChunkTopicBrief(id=row[0], name=row[1], relevance=float(row[2]))
        for row in topic_rows
    ]

    # Concepts associated with chunk
    concept_rows = db.execute(
        select(Concept.id, Concept.name)
        .join(ChunkConcept, ChunkConcept.concept_id == Concept.id)
        .where(ChunkConcept.chunk_id == chunk.id)
        .order_by(Concept.name.asc())
    ).all()
    concepts = [ChunkConceptBrief(id=row[0], name=row[1]) for row in concept_rows]

    return ChunkViewerResponse(
        chunk=ChunkDetail(
            id=chunk.id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            token_count=chunk.token_count,
            source_type=chunk.source_type,
            location=_get_location(chunk),
            section_title=chunk.section_title,
        ),
        source=ChunkSourceDetail(
            id=source.id,
            title=source.title,
            source_type=source.source_type,
            original_filename=source.original_filename,
            status=source.status,
        ),
        file_url=f"/api/v1/sources/{source.id}/file",
        viewer=viewer,
        media_url=media_url,
        seek_url=seek_url,
        previous=previous,
        next=next_val,
        topics=topics,
        concepts=concepts,
    )
