"""FastAPI authentication dependencies and permission helpers."""

from typing import Optional
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.student import Student
from app.services.auth.tokens import decode_token

# HTTPBearer with auto_error=False to suppress FastAPI's default 403 {"detail": ...} response
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_student(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[Student]:
    """Retrieve and validate the currently authenticated student from Bearer token.

    Behavior:
    - If Authorization header is missing:
      - When AUTH_REQUIRED=true: raises 401 'not_authenticated' with WWW-Authenticate header.
      - When AUTH_REQUIRED=false: returns None.
    - If Authorization header is present but malformed:
      - Raises 401 'not_authenticated' with WWW-Authenticate header.
    - If token is present:
      - Validates and decodes token (raises 401 'token_expired' or 'invalid_token').
      - Loads student from DB; if not found (deleted account), raises 401 'invalid_token'.
      - Returns the Student instance.
    """
    settings = get_settings()
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")

    # If credentials were not parsed by HTTPBearer:
    if credentials is None:
        if auth_header is not None:
            # Header was supplied but is malformed or not Bearer scheme
            raise AppError(
                "Not authenticated",
                code="not_authenticated",
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        # No Authorization header supplied
        if settings.auth_required:
            raise AppError(
                "Not authenticated",
                code="not_authenticated",
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

    token = credentials.credentials.strip()
    if not token:
        raise AppError(
            "Not authenticated",
            code="not_authenticated",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    student_id = decode_token(token)

    student = db.get(Student, student_id)
    if not student:
        raise AppError("Invalid token", code="invalid_token", status_code=401)

    return student


def require_same_student(current: Optional[Student], student_id: int) -> None:
    """Enforce that the currently authenticated student owns the requested resource.

    Args:
        current: Currently authenticated student (or None if auth disabled).
        student_id: Target student ID being accessed.

    Raises:
        AppError: 403 'forbidden_student' if AUTH_REQUIRED is True and IDs mismatch.
    """
    settings = get_settings()
    if settings.auth_required:
        if current is None or current.id != student_id:
            raise AppError(
                "You can only access your own data.",
                code="forbidden_student",
                status_code=403,
            )


def resolve_student_id(current: Optional[Student], provided: Optional[int]) -> int:
    """Resolve student ID from explicit input or current authenticated session.

    Args:
        current: Currently authenticated student (or None).
        provided: Optional explicit student ID from request query or body.

    Returns:
        int: The resolved student ID.

    Raises:
        AppError: 403 'forbidden_student' if provided ID does not match current student.
        AppError: 422 'student_id_required' if neither exists (only possible when AUTH_REQUIRED=false).
    """
    if provided is not None:
        require_same_student(current, provided)
        return provided
    if current is not None:
        return current.id
    raise AppError("student_id is required", code="student_id_required", status_code=422)
