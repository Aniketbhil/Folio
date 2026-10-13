import logging
from pathlib import Path
from typing import Any, Callable, Dict, List
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models.source import Chunk, Source
from app.services.ingestion.chunking import create_chunks_from_units
from app.services.ingestion.parsers.base import ParserResult
from app.services.ingestion.parsers.pdf import parse_pdf
from app.services.ingestion.parsers.pptx import parse_pptx
from app.services.ingestion.parsers.transcript import parse_transcript

logger = logging.getLogger(__name__)


class IngestionContext:
    """Carries execution state across ingestion stages."""

    def __init__(self, source_id: int) -> None:
        self.source_id = source_id
        self.source: Source = None  # type: ignore[assignment]
        self.parser_result: ParserResult = None  # type: ignore[assignment]
        self.chunks_data: List[Dict[str, Any]] = []


def _stage_parse(ctx: IngestionContext, db: Session) -> None:
    """Stage 1: Parse raw document into atomic units with source locations."""
    settings = get_settings()
    source = ctx.source

    source.status = "processing"
    source.stage = "parsing"
    source.progress = 10
    db.commit()

    file_path = source.file_path
    ext = Path(file_path).suffix.lower()

    if source.source_type == "pdf" or ext == ".pdf":
        result = parse_pdf(file_path)
    elif source.source_type == "pptx" or ext in (".pptx",):
        result = parse_pptx(file_path)
    elif source.source_type == "video_transcript" or ext in (".vtt", ".srt", ".txt", ".json"):
        result = parse_transcript(
            file_path,
            window_sec=settings.transcript_window_sec,
            chunk_target_tokens=settings.chunk_target_tokens,
        )
    else:
        raise AppError(f"Unsupported file type for ingestion: {ext}", code="unsupported_file_type")

    ctx.parser_result = result
    source.progress = 40
    db.commit()


def _stage_chunk(ctx: IngestionContext, db: Session) -> None:
    """Stage 2: Split units into bounded token chunks while preserving source metadata."""
    settings = get_settings()
    source = ctx.source

    source.stage = "chunking"
    source.progress = 50
    db.commit()

    ctx.chunks_data = create_chunks_from_units(
        units=ctx.parser_result.units,
        target_tokens=settings.chunk_target_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
    )


def _stage_save(ctx: IngestionContext, db: Session) -> None:
    """Stage 3: Persist chunk records and finalize source status."""
    source = ctx.source

    source.stage = "saving"
    source.progress = 80
    db.commit()

    # Bulk insert chunk models
    chunk_models: List[Chunk] = []
    for c_data in ctx.chunks_data:
        chunk = Chunk(
            course_id=source.course_id,
            source_id=source.id,
            chunk_index=c_data["chunk_index"],
            text=c_data["text"],
            source_type=c_data["source_type"],
            page_number=c_data["page_number"],
            slide_number=c_data["slide_number"],
            start_sec=c_data["start_sec"],
            end_sec=c_data["end_sec"],
            section_title=c_data["section_title"],
            token_count=c_data["token_count"],
            embedded=False,
        )
        chunk_models.append(chunk)

    db.add_all(chunk_models)

    # Finalize ready state
    source.status = "ready"
    source.stage = "done"
    source.progress = 100
    source.num_units = ctx.parser_result.num_units
    source.error = None

    # Merge metadata
    merged_meta = dict(source.meta or {})
    merged_meta.update(ctx.parser_result.meta)
    source.meta = merged_meta

    db.commit()
    logger.info(
        "Source %d ingestion completed: %d units, %d chunks created.",
        source.id,
        source.num_units,
        len(chunk_models),
    )


# Ordered stage list - easily extended in Prompt 3 for embeddings & topics
PIPELINE_STAGES: List[Callable[[IngestionContext, Session], None]] = [
    _stage_parse,
    _stage_chunk,
    _stage_save,
]


def run_ingestion(source_id: int) -> None:
    """Orchestrates document ingestion background job using an independent database session."""
    with SessionLocal() as db:
        source = db.get(Source, source_id)
        if not source:
            logger.error("Source id %d not found for ingestion pipeline.", source_id)
            return

        # Idempotency: clear any existing chunks for this source
        db.execute(delete(Chunk).where(Chunk.source_id == source_id))
        db.commit()

        ctx = IngestionContext(source_id=source_id)
        ctx.source = source

        current_stage = "parsing"
        try:
            for stage_fn in PIPELINE_STAGES:
                stage_fn(ctx, db)
        except Exception as exc:
            db.rollback()
            logger.exception("Ingestion failed for source %d at stage '%s': %s", source_id, source.stage, exc)

            # Cleanup partially saved chunks and record failure state
            try:
                with SessionLocal() as cleanup_db:
                    cleanup_db.execute(delete(Chunk).where(Chunk.source_id == source_id))
                    failed_source = cleanup_db.get(Source, source_id)
                    if failed_source:
                        failed_source.status = "failed"
                        # Record short human-readable error message (no stack trace)
                        if isinstance(exc, AppError):
                            failed_source.error = exc.message
                        else:
                            failed_source.error = str(exc) or "Failed to process document."
                    cleanup_db.commit()
            except Exception as cleanup_err:
                logger.exception("Failed to update failure state for source %d: %s", source_id, cleanup_err)
