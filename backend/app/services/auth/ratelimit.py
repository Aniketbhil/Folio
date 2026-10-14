"""In-memory rate limiter tracking failed login attempts.

NOTE: This tracker is single-process only (stores state in local process memory protected
by a threading Lock). For multi-process, clustered, or containerized deployments, a distributed
cache such as Redis should be used instead.
"""

import threading
import time
from typing import Dict, List, Tuple

from app.core.config import get_settings
from app.core.errors import AppError

_lock = threading.Lock()
# Key: (lowercased_email, client_ip) -> list of failure timestamps
_failed_attempts: Dict[Tuple[str, str], List[float]] = {}


def check_login_rate_limit(email: str, client_ip: str) -> None:
    """Check if the given email and client IP are currently locked out.

    Args:
        email: Lowercased or raw email address.
        client_ip: Client IP address string.

    Raises:
        AppError: 429 'too_many_attempts' if failed attempts meet or exceed limit in lockout window.
    """
    settings = get_settings()
    key = (email.strip().lower(), client_ip.strip())
    now = time.time()
    window = settings.auth_lockout_minutes * 60

    with _lock:
        if key in _failed_attempts:
            # Filter out timestamps older than the lockout window
            _failed_attempts[key] = [t for t in _failed_attempts[key] if now - t < window]
            if len(_failed_attempts[key]) >= settings.auth_max_failed_attempts:
                raise AppError(
                    "Too many failed login attempts. Please try again later.",
                    code="too_many_attempts",
                    status_code=429,
                )


def record_failed_login(email: str, client_ip: str) -> None:
    """Record a failed login attempt for the email and client IP."""
    key = (email.strip().lower(), client_ip.strip())
    now = time.time()
    with _lock:
        if key not in _failed_attempts:
            _failed_attempts[key] = []
        _failed_attempts[key].append(now)


def clear_failed_logins(email: str, client_ip: str) -> None:
    """Clear failed login attempts following a successful authentication."""
    key = (email.strip().lower(), client_ip.strip())
    with _lock:
        _failed_attempts.pop(key, None)
