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
    source.num_units = ctx.parser_result.num_units

    # Merge metadata
    merged_meta = dict(source.meta or {})
    merged_meta.update(ctx.parser_result.meta)
    source.meta = merged_meta
    db.commit()


def _stage_embedding(ctx: IngestionContext, db: Session) -> None:
    """Stage 4: Compute text embeddings and insert into persistent vector store."""
    from app.services.llm import get_llm_client
    from app.services.vector_store import get_vector_store

    source = ctx.source
    source.stage = "embedding"
    source.progress = 85
    db.commit()

    llm = get_llm_client()
    vstore = get_vector_store()

    # Idempotent: delete previous vectors for this source
    vstore.delete_by_source(source.id)

    chunks = list(
        db.scalars(
            select(Chunk)
            .where(Chunk.source_id == source.id)
            .order_by(Chunk.chunk_index.asc())
        ).all()
    )

    if chunks:
        embed_texts_list = [
            (((c.section_title + "\n") if c.section_title else "") + c.text)[:2000]
            for c in chunks
        ]
        embeddings = llm.embed_texts(embed_texts_list, task="document")

        items_to_add: List[Dict[str, Any]] = []
        for chunk_obj, emb in zip(chunks, embeddings):
            items_to_add.append({
                "chunk_id": chunk_obj.id,
                "course_id": chunk_obj.course_id,
                "source_id": chunk_obj.source_id,
                "text": chunk_obj.text,
                "embedding": emb,
            })
            chunk_obj.embedded = True

        vstore.add_chunks(items_to_add)

    source.progress = 95
    source.status = "ready"
    source.stage = "done"
    source.progress = 100
    source.error = None
    db.commit()

    logger.info(
        "Source %d ingestion completed: %d units, %d chunks embedded and saved.",
        source.id,
        source.num_units,
        len(chunks),
    )


def _stage_captioning(ctx: IngestionContext, db: Session) -> None:
    """Stage 3b: Extract figures/diagrams and compute descriptive captions if enabled."""
    settings = get_settings()
    if not settings.image_caption_enabled:
        return

    source = ctx.source
    source.stage = "captioning"
    source.progress = 82
    db.commit()

    import hashlib
    from concurrent.futures import ThreadPoolExecutor
    from app.services.llm import get_llm_client

    llm = get_llm_client()
    file_path = source.file_path
    ext = Path(file_path).suffix.lower()

    extracted_images: List[tuple[int, bytes, str, str]] = []
    page_counts: Dict[str, set[int]] = {}
    total_pages_or_slides = 1

    try:
        if source.source_type == "pdf" or ext == ".pdf":
            import fitz
            doc = fitz.open(file_path)
            total_pages_or_slides = len(doc)
            for pno, page in enumerate(doc, start=1):
                image_list = page.get_images()
                for img_info in image_list:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)
                    if width < settings.image_min_px or height < settings.image_min_px:
                        continue
                    img_bytes = base_image["image"]
                    ext_img = base_image.get("ext", "png")
                    mime = f"image/{ext_img}" if ext_img != "jpg" else "image/jpeg"
                    h = hashlib.sha256(img_bytes).hexdigest()
                    page_counts.setdefault(h, set()).add(pno)
                    first_text = page.get_text()[:60]
                    extracted_images.append((pno, img_bytes, mime, first_text))
            doc.close()

        elif source.source_type == "pptx" or ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(file_path)
            total_pages_or_slides = len(prs.slides)
            for sidx, slide in enumerate(prs.slides, start=1):
                slide_text = ""
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        slide_text += shape.text + " "

                def _extract_from_shape(shape, snum):
                    if shape.shape_type == 13:  # PICTURE
                        image = shape.image
                        img_bytes = image.blob
                        w_px = getattr(shape, "width", 0) / 9525 if getattr(shape, "width", 0) else 200
                        h_px = getattr(shape, "height", 0) / 9525 if getattr(shape, "height", 0) else 200
                        if w_px >= settings.image_min_px and h_px >= settings.image_min_px:
                            mime = image.content_type or "image/png"
                            h = hashlib.sha256(img_bytes).hexdigest()
                            page_counts.setdefault(h, set()).add(snum)
                            extracted_images.append((snum, img_bytes, mime, slide_text[:60]))
                    elif shape.shape_type == 6:  # GROUP
                        for sub_shape in shape.shapes:
                            _extract_from_shape(sub_shape, snum)

                for shape in slide.shapes:
                    _extract_from_shape(shape, sidx)

        repeat_threshold = max(2, int(total_pages_or_slides * 0.30))
        valid_candidates = []
        seen_on_page = set()
        skipped_count = 0

        for pnum, bts, mime, hint in extracted_images:
            h = hashlib.sha256(bts).hexdigest()
            if len(page_counts.get(h, set())) > repeat_threshold:
                skipped_count += 1
                continue
            if (pnum, h) in seen_on_page:
                continue
            seen_on_page.add((pnum, h))
            valid_candidates.append((pnum, bts, mime, hint))

        valid_candidates = valid_candidates[: settings.image_caption_max_per_source]

        chunks = list(
            db.scalars(
                select(Chunk).where(Chunk.source_id == source.id).order_by(Chunk.chunk_index.asc())
            ).all()
        )

        def _do_caption(item):
            pnum, bts, mime, hint = item
            cap = llm.caption_image(image_bytes=bts, mime=mime, context_hint=f"page/slide {pnum}: {hint}")
            return pnum, cap

        captioned_count = 0
        if valid_candidates:
            with ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(_do_caption, valid_candidates))

            for pnum, cap in results:
                if not cap or cap.strip().upper() == "DECORATIVE":
                    skipped_count += 1
                    continue

                owning_chunk = None
                for c in chunks:
                    if (c.page_number == pnum) or (c.slide_number == pnum):
                        owning_chunk = c
                        break

                if owning_chunk:
                    owning_chunk.image_caption = cap.strip()
                    owning_chunk.text = f"{owning_chunk.text}\n\nFigure: {cap.strip()}"
                    captioned_count += 1

        meta = dict(source.meta or {})
        meta["captioned_count"] = captioned_count
        meta["skipped_images"] = skipped_count
        source.meta = meta
        db.commit()

    except Exception as exc:
        logger.warning("Image captioning stage encountered error (skipped): %s", exc)


import threading

_INGEST_SEMAPHORE = threading.Semaphore(get_settings().ingest_max_concurrent)
_ACTIVE_INGESTION_COUNT = 0
_ACTIVE_LOCK = threading.Lock()


def get_active_ingestion_count() -> int:
    """Return number of currently active ingestion jobs."""
    with _ACTIVE_LOCK:
        return _ACTIVE_INGESTION_COUNT


# Ordered stage list
PIPELINE_STAGES: List[Callable[[IngestionContext, Session], None]] = [
    _stage_parse,
    _stage_chunk,
    _stage_save,
    _stage_captioning,
    _stage_embedding,
]


def run_ingestion(source_id: int) -> None:
    """Orchestrates document ingestion background job using an independent database session."""
    _INGEST_SEMAPHORE.acquire()
    global _ACTIVE_INGESTION_COUNT
    with _ACTIVE_LOCK:
        _ACTIVE_INGESTION_COUNT += 1

    try:
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

            course_id = source.course_id
            current_stage = "parsing"
            try:
                for stage_fn in PIPELINE_STAGES:
                    stage_fn(ctx, db)

                # Auto-trigger KB build if configured and no other sources are processing
                settings = get_settings()
                if settings.auto_build_kb:
                    try:
                        from sqlalchemy import func
                        with SessionLocal() as check_db:
                            other_active = check_db.scalar(
                                select(func.count(Source.id)).where(
                                    Source.course_id == course_id,
                                    Source.id != source_id,
                                    Source.status.in_(["queued", "processing"]),
                                )
                            ) or 0
                        if other_active == 0:
                            from app.services.kb.service import get_kb_service
                            get_kb_service().request_build(course_id)
                    except Exception as kb_trigger_err:
                        logger.warning("Could not auto-trigger KB build for course %d: %s", course_id, kb_trigger_err)
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
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_INGESTION_COUNT = max(0, _ACTIVE_INGESTION_COUNT - 1)
        _INGEST_SEMAPHORE.release()
