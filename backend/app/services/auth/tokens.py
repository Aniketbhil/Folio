"""JWT token generation and verification services."""

from datetime import datetime, timezone
from typing import Tuple
import jwt

from app.core.config import get_settings
from app.core.errors import AppError


def create_access_token(student_id: int) -> Tuple[str, int]:
    """Create a signed JWT access token for a student.

    Args:
        student_id: Student identifier to store in the 'sub' claim.

    Returns:
        Tuple of (token_string, expires_in_seconds).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_in_seconds = settings.jwt_expire_minutes * 60
    exp = int(now.timestamp()) + expires_in_seconds

    payload = {
        "sub": str(student_id),
        "iat": int(now.timestamp()),
        "exp": exp,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in_seconds


def decode_token(token: str) -> int:
    """Decode and validate a JWT access token.

    Args:
        token: Raw JWT token string.

    Returns:
        int: The student ID extracted from the 'sub' claim.

    Raises:
        AppError: 401 'token_expired' if token timestamp is in the past.
        AppError: 401 'invalid_token' if malformed, signature mismatch, or bad claims.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        if sub is None:
            raise AppError("Invalid token", code="invalid_token", status_code=401)
        return int(sub)
    except jwt.ExpiredSignatureError:
        raise AppError("Token has expired", code="token_expired", status_code=401)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise AppError("Invalid token", code="invalid_token", status_code=401)
