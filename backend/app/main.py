import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

import app.models  # noqa: F401 - ensure all models are registered on Base.metadata
from app.api.routes import assessments, chunks, courses, dev, health, kb, learner, meta, sources, students, tutor
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.session import Base, SessionLocal, engine, run_sqlite_migrations
from app.models.course import Course
from app.models.source import Source
from app.services.llm import get_llm_client
from app.services.vector_store import get_vector_store
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("folio")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = req_id

        settings = get_settings()
        log_msg = f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms) [request_id={req_id}]"
        if duration_ms > settings.slow_request_ms:
            logger.warning("SLOW REQUEST: %s", log_msg)
        else:
            logger.info(log_msg)

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle handler for the application."""
    settings = get_settings()

    # 1. Ensure required storage directories exist
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    chroma_path = Path(settings.chroma_dir)
    chroma_path.mkdir(parents=True, exist_ok=True)

    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite:///", "").replace("sqlite://", "")
        if db_path and not db_path.startswith(":memory:"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # 2. Create database tables and apply sqlite migrations
    Base.metadata.create_all(bind=engine)
    run_sqlite_migrations(engine)
    logger.info("Database schema initialized successfully.")

    # 3. Startup recovery: mark interrupted sources and building courses as failed
    try:
        with SessionLocal() as db:
            interrupted_sources = list(
                db.scalars(
                    select(Source).where(Source.status.in_(["queued", "processing"]))
                ).all()
            )
            for src in interrupted_sources:
                src.status = "failed"
                src.error = "Interrupted by a server restart. Use retry."
            if interrupted_sources:
                logger.info("Marked %d interrupted source(s) as failed.", len(interrupted_sources))

            building_courses = list(
                db.scalars(
                    select(Course).where(Course.kb_status == "building")
                ).all()
            )
            for crs in building_courses:
                crs.kb_status = "failed"
                crs.kb_error = "Interrupted by a server restart. Use rebuild."
            if building_courses:
                logger.info("Marked %d interrupted building course(s) as failed.", len(building_courses))

            if interrupted_sources or building_courses:
                db.commit()
    except Exception as exc:
        logger.warning("Failed during startup recovery check: %s", exc)

    # 4. Pre-warm services
    llm = get_llm_client()
    vstore = get_vector_store()
    logger.info(
        "Services initialized (LLM mock: %s, Chroma collections: %d, %d)",
        settings.llm_mock,
        vstore.chunks_collection.count(),
        vstore.questions_collection.count(),
    )

    yield

    logger.info("Folio backend shutdown complete.")


def create_app() -> FastAPI:
    """Application factory configuring routes, CORS, and error handlers."""
    settings = get_settings()

    app = FastAPI(
        title="Folio Backend",
        description="Source-grounded AI study companion API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Register Logging Middleware & CORS
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register global error handlers
    register_error_handlers(app)

    # Include API routes under /api/v1 prefix
    from fastapi import APIRouter

    api_v1_router = APIRouter(prefix="/api/v1")
    api_v1_router.include_router(health.router)
    api_v1_router.include_router(meta.router)
    api_v1_router.include_router(students.router)
    api_v1_router.include_router(courses.router)
    api_v1_router.include_router(sources.router)
    api_v1_router.include_router(kb.router)
    api_v1_router.include_router(chunks.router)
    api_v1_router.include_router(tutor.router)
    api_v1_router.include_router(assessments.router)
    api_v1_router.include_router(learner.router)

    if settings.debug:
        api_v1_router.include_router(dev.router)
        # Also mount on /dev for direct convenience
        app.include_router(dev.router)

    app.include_router(api_v1_router)

    # Also mount health directly on /health for root health checkers
    app.include_router(health.router)

    return app


app = create_app()
