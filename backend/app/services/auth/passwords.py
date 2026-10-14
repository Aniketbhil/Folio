"""Password validation, hashing, and verification using Argon2."""

from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.errors import AppError

# Initialize Argon2 password hasher
_hasher = PasswordHasher()

# Fixed dummy hash for constant-time dummy verification on unknown emails
DUMMY_HASH = _hasher.hash("dummy_constant_password_for_timing_defense")


def validate_password(pw: str) -> None:
    """Validate password strength according to security rules.

    Rules:
    - Length between 8 and 128 characters inclusive
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one symbol (any non-alphanumeric, non-whitespace character)
    - Digits are not strictly required

    Raises:
        AppError: 422 'weak_password' with a message listing the failed rules.
    """
    reasons: list[str] = []

    if len(pw) < 8:
        reasons.append("be at least 8 characters")
    elif len(pw) > 128:
        reasons.append("be at most 128 characters")

    if not any(c.isupper() for c in pw):
        reasons.append("include an uppercase letter")

    if not any(c.islower() for c in pw):
        reasons.append("include a lowercase letter")

    # Symbol: any character that is not a letter, digit, or whitespace (space is not a symbol)
    if not any(not c.isalnum() and not c.isspace() for c in pw):
        reasons.append("include a symbol")

    if reasons:
        if len(reasons) == 1:
            msg = f"Password must {reasons[0]}."
        elif len(reasons) == 2:
            msg = f"Password must {reasons[0]} and {reasons[1]}."
        else:
            msg = f"Password must {', '.join(reasons[:-1])} and {reasons[-1]}."
        raise AppError(message=msg, code="weak_password", status_code=422)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2. Never logs passwords or hashes."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_pw: Optional[str]) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Returns False on any verification error (mismatch, invalid hash, None, etc.).
    Never logs passwords or hashes.
    """
    if not hashed_pw:
        return False
    try:
        return _hasher.verify(hashed_pw, password)
    except (VerificationError, InvalidHashError, ValueError, Exception):
        return False


def check_needs_rehash(hashed_pw: Optional[str]) -> bool:
    """Check if the hash was created with older parameters and needs updating."""
    if not hashed_pw:
        return False
    try:
        return _hasher.check_needs_rehash(hashed_pw)
    except Exception:
        return False
