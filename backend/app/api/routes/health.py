from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.common import HealthResponse
from app.services.vector_store import get_vector_store

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
) -> HealthResponse:
    """Health check validating database connectivity, vector store state, and LLM mode."""
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

    return HealthResponse(
        status=overall_status,
        db=db_status,
        vector_store=vector_status,
        llm_mode=llm_mode,
        version="0.1.0",
    )
