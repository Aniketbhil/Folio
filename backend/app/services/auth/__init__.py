"""Authentication services package."""

from app.services.auth.dependencies import (
    get_current_student,
    require_same_student,
    resolve_student_id,
)
from app.services.auth.passwords import (
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
from app.services.auth.tokens import create_access_token, decode_token

__all__ = [
    "validate_password",
    "hash_password",
    "verify_password",
    "check_needs_rehash",
    "create_access_token",
    "decode_token",
    "check_login_rate_limit",
    "record_failed_login",
    "clear_failed_logins",
    "get_current_student",
    "require_same_student",
    "resolve_student_id",
]
