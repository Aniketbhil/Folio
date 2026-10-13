import hashlib
from pathlib import Path
import re
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.course import Course
from app.models.source import Chunk, Source
from app.models.topic import ChunkConcept, ChunkTopic, Concept, Topic, TopicPrereq
from app.schemas.source import ChunkRead, SourceDeleteResponse, SourceRead
from app.services.ingestion.pipeline import run_ingestion
from app.services.kb.service import get_kb_service
from app.services.vector_store import get_vector_store

router = APIRouter(tags=["sources"])

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".vtt": "video_transcript",
    ".srt": "video_transcript",
    ".txt": "video_transcript",
    ".json": "video_transcript",
}

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "vtt": "text/vtt",
    "srt": "text/plain",
    "txt": "text/plain",
    "json": "application/json",
}


def _sanitize_filename(filename: str) -> str:
    """Sanitize client-provided filename to prevent directory traversal or unsafe path chars."""
    basename = Path(filename or "document").name
    stem = Path(basename).stem
    ext = Path(basename).suffix.lower()
    clean_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", stem).strip("_")
    if not clean_stem:
        clean_stem = "upload"
    return f"{clean_stem}{ext}"


@router.post(
    "/courses/{course_id}/sources",
    response_model=SourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_course_source(
    course_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    media_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> SourceRead:
    """Upload and schedule ingestion for a course document (PDF, PPTX, or transcript)."""
    settings = get_settings()

    # 1. Validate course existence
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    # 2. Validate file extension
    raw_filename = file.filename or ""
    ext = Path(raw_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(
            f"Unsupported file type '{ext}'. Allowed types: pdf, pptx, vtt, srt, txt, json",
            code="unsupported_file_type",
            status_code=415,
        )
    source_type = ALLOWED_EXTENSIONS[ext]

    # 3. Read file content and validate size
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError(
            f"File exceeds maximum upload limit of {settings.max_upload_mb} MB",
            code="file_too_large",
            status_code=413,
        )
    if len(content) == 0:
        raise AppError("Uploaded file is empty", code="empty_file", status_code=400)

    # 4. Compute SHA256 and verify uniqueness within course
    file_sha256 = hashlib.sha256(content).hexdigest()
    existing_sources = db.scalars(
        select(Source).where(Source.course_id == course_id)
    ).all()
    for s in existing_sources:
        if s.meta and s.meta.get("sha256") == file_sha256:
            raise AppError(
                f"A file with the same content already exists in this course (source id {s.id})",
                code="duplicate_source",
                status_code=409,
            )

    # Validate media_url if provided
    source_meta: dict = {"sha256": file_sha256}
    if media_url is not None:
        trimmed_url = media_url.strip()
        if trimmed_url:
            if not (trimmed_url.startswith("http://") or trimmed_url.startswith("https://")):
                raise AppError(
                    "media_url must start with http:// or https://",
                    code="invalid_media_url",
                    status_code=400,
                )
            source_meta["media_url"] = trimmed_url

    # 5. Sanitize and prepare destination path
    sanitized_name = _sanitize_filename(raw_filename)
    resolved_title = title.strip() if title and title.strip() else Path(sanitized_name).stem

    # Create temporary DB record to obtain primary key ID
    source = Source(
        course_id=course_id,
        title=resolved_title,
        source_type=source_type,
        original_filename=raw_filename,
        file_path="",  # populated below
        status="queued",
        progress=0,
        num_units=0,
        meta=source_meta,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    # Save to disk: UPLOAD_DIR/{course_id}/{source_id}_{sanitized_name}
    course_upload_dir = Path(settings.upload_dir) / str(course_id)
    course_upload_dir.mkdir(parents=True, exist_ok=True)
    destination_path = course_upload_dir / f"{source.id}_{sanitized_name}"
    destination_path.write_bytes(content)

    source.file_path = str(destination_path)
    db.commit()
    db.refresh(source)

    # 6. Schedule background ingestion
    background_tasks.add_task(run_ingestion, source.id)

    return SourceRead(
        id=source.id,
        course_id=source.course_id,
        title=source.title,
        source_type=source.source_type,
        original_filename=source.original_filename,
        file_path=source.file_path,
        status=source.status,
        stage=source.stage,
        progress=source.progress,
        error=source.error,
        num_units=source.num_units,
        meta=source.meta or {},
        created_at=source.created_at,
        chunk_count=0,
    )


@router.get("/courses/{course_id}/sources", response_model=List[SourceRead])
def list_course_sources(
    course_id: int,
    db: Session = Depends(get_db),
) -> List[SourceRead]:
    """List all sources associated with a course, newest first."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    sources = list(
        db.scalars(
            select(Source)
            .where(Source.course_id == course_id)
            .order_by(Source.created_at.desc())
        ).all()
    )

    results: List[SourceRead] = []
    for s in sources:
        cnt = db.scalar(select(func.count(Chunk.id)).where(Chunk.source_id == s.id)) or 0
        results.append(
            SourceRead(
                id=s.id,
                course_id=s.course_id,
                title=s.title,
                source_type=s.source_type,
                original_filename=s.original_filename,
                file_path=s.file_path,
                status=s.status,
                stage=s.stage,
                progress=s.progress,
                error=s.error,
                num_units=s.num_units,
                meta=s.meta or {},
                created_at=s.created_at,
                chunk_count=cnt,
            )
        )
    return results


@router.get("/sources/{source_id}", response_model=SourceRead)
def get_source(
    source_id: int,
    db: Session = Depends(get_db),
) -> SourceRead:
    """Retrieve source details and current ingestion status."""
    source = db.get(Source, source_id)
    if not source:
        raise AppError(
            f"Source with id {source_id} not found",
            code="source_not_found",
            status_code=404,
        )

    cnt = db.scalar(select(func.count(Chunk.id)).where(Chunk.source_id == source.id)) or 0
    return SourceRead(
        id=source.id,
        course_id=source.course_id,
        title=source.title,
        source_type=source.source_type,
        original_filename=source.original_filename,
        file_path=source.file_path,
        status=source.status,
        stage=source.stage,
        progress=source.progress,
        error=source.error,
        num_units=source.num_units,
        meta=source.meta or {},
        created_at=source.created_at,
        chunk_count=cnt,
    )


@router.get("/sources/{source_id}/file")
def get_source_file(
    source_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download original document file with inline disposition."""
    source = db.get(Source, source_id)
    if not source:
        raise AppError(
            f"Source with id {source_id} not found",
            code="source_not_found",
            status_code=404,
        )

    file_path = Path(source.file_path)
    if not file_path.is_file():
        raise AppError(
            f"Physical file for source {source_id} is missing from storage",
            code="file_not_found",
            status_code=404,
        )

    ext = file_path.suffix.lstrip(".").lower()
    media_type = MEDIA_TYPES.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{source.original_filename}"'},
    )


@router.get("/sources/{source_id}/chunks", response_model=List[ChunkRead])
def list_source_chunks(
    source_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[ChunkRead]:
    """Inspect paginated chunks extracted for a specific source."""
    source = db.get(Source, source_id)
    if not source:
        raise AppError(
            f"Source with id {source_id} not found",
            code="source_not_found",
            status_code=404,
        )

    stmt = (
        select(Chunk)
        .where(Chunk.source_id == source_id)
        .order_by(Chunk.chunk_index.asc())
        .limit(max(1, min(limit, 200)))
        .offset(max(0, offset))
    )
    chunks = list(db.scalars(stmt).all())
    return [ChunkRead.model_validate(c) for c in chunks]


@router.post("/sources/{source_id}/retry", response_model=SourceRead)
def retry_source_ingestion(
    source_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SourceRead:
    """Retry ingestion for a failed source."""
    source = db.get(Source, source_id)
    if not source:
        raise AppError(
            f"Source with id {source_id} not found",
            code="source_not_found",
            status_code=404,
        )

    if source.status != "failed":
        raise AppError(
            f"Cannot retry source in status '{source.status}'; retry is only allowed for failed sources",
            code="invalid_state",
            status_code=409,
        )

    # Reset state and re-queue
    source.status = "queued"
    source.stage = None
    source.progress = 0
    source.error = None
    db.commit()
    db.refresh(source)

    background_tasks.add_task(run_ingestion, source.id)

    cnt = db.scalar(select(func.count(Chunk.id)).where(Chunk.source_id == source.id)) or 0
    return SourceRead(
        id=source.id,
        course_id=source.course_id,
        title=source.title,
        source_type=source.source_type,
        original_filename=source.original_filename,
        file_path=source.file_path,
        status=source.status,
        stage=source.stage,
        progress=source.progress,
        error=source.error,
        num_units=source.num_units,
        meta=source.meta or {},
        created_at=source.created_at,
        chunk_count=cnt,
    )


@router.delete("/sources/{source_id}", response_model=SourceDeleteResponse)
def delete_source(
    source_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SourceDeleteResponse:
    """Delete a source file, vector database entries, and database chunks."""
    source = db.get(Source, source_id)
    if not source:
        raise AppError(
            f"Source with id {source_id} not found",
            code="source_not_found",
            status_code=404,
        )

    course_id = source.course_id

    # 1. Delete physical file from storage
    if source.file_path:
        p = Path(source.file_path)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    # 2. Delete vectors from Chroma
    try:
        store = get_vector_store()
        store.delete_by_source(source_id)
    except Exception:
        pass

    # 3. Delete database record (chunks cascade delete automatically)
    db.delete(source)
    db.commit()

    # 4. KB trigger / cleanup
    remaining_chunks = (
        db.scalar(select(func.count(Chunk.id)).where(Chunk.course_id == course_id))
        or 0
    )

    if remaining_chunks > 0:
        background_tasks.add_task(get_kb_service().request_build, course_id)
    else:
        course = db.get(Course, course_id)
        if course:
            course.kb_status = "empty"
            course.kb_error = None
            course.kb_built_at = None
            db.execute(delete(TopicPrereq).where(TopicPrereq.course_id == course_id))
            db.execute(
                delete(ChunkTopic).where(
                    ChunkTopic.topic_id.in_(
                        select(Topic.id).where(Topic.course_id == course_id)
                    )
                )
            )
            db.execute(
                delete(ChunkConcept).where(
                    ChunkConcept.concept_id.in_(
                        select(Concept.id).where(Concept.course_id == course_id)
                    )
                )
            )
            db.execute(delete(Concept).where(Concept.course_id == course_id))
            db.execute(
                update(Topic).where(Topic.course_id == course_id).values(parent_id=None)
            )
            db.execute(delete(Topic).where(Topic.course_id == course_id))
            db.commit()

    return SourceDeleteResponse(deleted=True)
