import time
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.course import Course
from app.models.source import Chunk, Source
from app.models.student import Student
from app.schemas.common import HealthCounts, HealthResponse
from app.services.ingestion.pipeline import get_active_ingestion_count
from app.services.vector_store import get_vector_store

router = APIRouter(tags=["Health"])

_APP_START_TIME = time.time()


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
) -> HealthResponse:
    """Health check validating database connectivity, vector store state, and system counts."""
    settings = get_settings()

    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    vector_status = "ok"
    try:
        store = get_vector_store()
        _ = store.chunks_collection.count()
    except Exception:
        vector_status = "error"

    llm_mode = "mock" if settings.llm_mock else "live"
    overall_status = "ok" if db_status == "ok" and vector_status == "ok" else "degraded"

    # Aggregated counts
    try:
        student_cnt = db.scalar(select(func.count(Student.id))) or 0
        course_cnt = db.scalar(select(func.count(Course.id))) or 0
        source_cnt = db.scalar(select(func.count(Source.id))) or 0
        chunk_cnt = db.scalar(select(func.count(Chunk.id))) or 0
        kb_building_cnt = (
            db.scalar(select(func.count(Course.id)).where(Course.kb_status == "building")) or 0
        )
    except Exception:
        student_cnt = 0
        course_cnt = 0
        source_cnt = 0
        chunk_cnt = 0
        kb_building_cnt = 0

    ingestion_active_cnt = get_active_ingestion_count()

    return HealthResponse(
        status=overall_status,
        db=db_status,
        vector_store=vector_status,
        llm_mode=llm_mode,
        version="0.1.0",
        uptime_sec=round(time.time() - _APP_START_TIME, 2),
        counts=HealthCounts(
            students=student_cnt,
            courses=course_cnt,
            sources=source_cnt,
            chunks=chunk_cnt,
        ),
        kb_building_courses=kb_building_cnt,
        ingestion_active=ingestion_active_cnt,
    )
