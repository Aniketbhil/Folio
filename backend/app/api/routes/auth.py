"""Authentication API routes (signup, login, me, change-password)."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.student import Student
from app.schemas.auth import (
    AuthResponse,
    AuthStudent,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    SignupRequest,
)
from app.services.auth.dependencies import get_current_student
from app.services.auth.passwords import (
    DUMMY_HASH,
    check_needs_rehash,
    hash_password,
    validate_password,
    verify_password,
)
from app.services.auth.ratelimit import (
    check_login_rate_limit,
    clear_failed_logins,
    record_failed_login,
)
from app.services.auth.tokens import create_access_token

router = APIRouter(tags=["auth"])


def _extract_client_ip(request: Request) -> str:
    """Extract client IP from request headers or socket info."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


@router.post(
    "/auth/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Register a new student account, hash credentials, and issue an access token."""
    normalized_email = payload.email.strip().lower()

    # Check for existing account with the same email (case-insensitive)
    existing = db.scalar(
        select(Student).where(func.lower(Student.email) == normalized_email)
    )
    if existing:
        raise AppError(
            "An account with this email already exists.",
            code="email_taken",
            status_code=409,
        )

    # Validate password complexity rules
    validate_password(payload.password)

    # Hash password with Argon2
    hashed = hash_password(payload.password)

    student = Student(
        name=payload.name.strip(),
        email=normalized_email,
        password_hash=hashed,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    token, expires_in = create_access_token(student.id)

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        student=AuthStudent(id=student.id, name=student.name, email=student.email),
    )


@router.post(
    "/auth/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Authenticate student credentials, update last login, and issue an access token."""
    client_ip = _extract_client_ip(request)
    normalized_email = payload.email.strip().lower()

    # Enforce brute-force rate limiting
    check_login_rate_limit(normalized_email, client_ip)

    student = db.scalar(
        select(Student).where(func.lower(Student.email) == normalized_email)
    )

    # Timing-safe failure path for unknown user or legacy accounts without password_hash
    if student is None or student.password_hash is None:
        verify_password(payload.password, DUMMY_HASH)
        record_failed_login(normalized_email, client_ip)
        raise AppError(
            "Incorrect email or password.",
            code="invalid_credentials",
            status_code=401,
        )

    # Verify password against student's Argon2 hash
    if not verify_password(payload.password, student.password_hash):
        record_failed_login(normalized_email, client_ip)
        raise AppError(
            "Incorrect email or password.",
            code="invalid_credentials",
            status_code=401,
        )

    # Authentication succeeded: clear failed logins and update login record
    clear_failed_logins(normalized_email, client_ip)

    if check_needs_rehash(student.password_hash):
        student.password_hash = hash_password(payload.password)

    student.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(student)

    token, expires_in = create_access_token(student.id)

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        student=AuthStudent(id=student.id, name=student.name, email=student.email),
    )


@router.get(
    "/auth/me",
    response_model=AuthStudent,
    status_code=status.HTTP_200_OK,
)
def get_current_user_profile(
    current_student: Optional[Student] = Depends(get_current_student),
) -> AuthStudent:
    """Return the profile of the currently authenticated student."""
    if current_student is None:
        raise AppError(
            "Not authenticated",
            code="not_authenticated",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthStudent(
        id=current_student.id,
        name=current_student.name,
        email=current_student.email,
    )


@router.post(
    "/auth/change-password",
    response_model=ChangePasswordResponse,
    status_code=status.HTTP_200_OK,
)
def change_password(
    payload: ChangePasswordRequest,
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> ChangePasswordResponse:
    """Change the password for the currently authenticated student."""
    if current_student is None:
        raise AppError(
            "Not authenticated",
            code="not_authenticated",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify current password
    if not verify_password(payload.current_password, current_student.password_hash):
        raise AppError(
            "Incorrect email or password.",
            code="invalid_credentials",
            status_code=401,
        )

    # Validate new password strength
    validate_password(payload.new_password)

    # Ensure new password differs from current
    if payload.new_password == payload.current_password:
        raise AppError(
            "New password must be different.",
            code="weak_password",
            status_code=422,
        )

    # Update password hash
    current_student.password_hash = hash_password(payload.new_password)
    db.commit()

    return ChangePasswordResponse(changed=True)
