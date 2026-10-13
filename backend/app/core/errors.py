import logging
from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application exception with error code and HTTP status code."""

    def __init__(
        self,
        message: str,
        code: str = "app_error",
        status_code: int = 400,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom AppError exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic / FastAPI request validation errors."""
    error_messages: list[str] = []
    for err in exc.errors():
        loc_parts = [str(part) for part in err.get("loc", []) if part != "body"]
        loc = ".".join(loc_parts)
        msg = err.get("msg", "Invalid input")
        error_messages.append(f"{loc}: {msg}" if loc else msg)
    message = "; ".join(error_messages) if error_messages else "Validation failed"
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": message}},
    )


def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard Starlette / FastAPI HTTPExceptions."""
    if exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 405:
        code = "method_not_allowed"
    elif exc.status_code == 413:
        code = "file_too_large"
    elif exc.status_code == 415:
        code = "unsupported_file_type"
    elif exc.status_code == 422:
        code = "validation_error"
    else:
        code = "http_error"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail)}},
    )


def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all error handler for unexpected server errors."""
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Internal server error"}},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all custom error handlers onto the FastAPI application instance."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
