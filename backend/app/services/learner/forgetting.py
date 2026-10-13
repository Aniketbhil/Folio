"""Forgetting curve and memory retention pure functions.

Implements the Ebbinghaus forgetting model parameterized by practice count:
- stability_days(correct_count) = min(FORGET_MAX_DAYS, FORGET_BASE_DAYS * (1 + FORGET_PER_CORRECT * correct_count))
- retrievability(days_since, correct_count) = exp(-days_since / stability_days)
- effective_mastery(p_mastery, last_practiced_at, correct_count, now)
"""

import math
from datetime import datetime, timezone
from typing import Optional

from app.core.config import get_settings


def stability_days(correct_count: int) -> float:
    """Calculate memory stability in days based on the number of correct answers."""
    settings = get_settings()
    c = max(0, int(correct_count))
    stab = settings.forget_base_days * (1.0 + settings.forget_per_correct * c)
    return float(min(settings.forget_max_days, stab))


def retrievability(days_since: float, correct_count: int) -> float:
    """Calculate retrieval probability after a given number of days since last practice."""
    if days_since <= 0.0:
        return 1.0
    stab = stability_days(correct_count)
    if stab <= 0.0:
        return 0.0
    return float(math.exp(-float(days_since) / stab))


def effective_mastery(
    p_mastery: float,
    last_practiced_at: Optional[datetime],
    correct_count: int,
    now: Optional[datetime] = None,
) -> float:
    """Calculate decayed effective mastery.

    Rules:
    - If last_practiced_at is None, no decay occurs.
    - If p_mastery > BKT_P_INIT:
        decay towards prior: BKT_P_INIT + (p_mastery - BKT_P_INIT) * retrievability
      else:
        p_mastery (decay never lowers below prior and never raises stored low mastery)
    """
    settings = get_settings()
    p = float(p_mastery)
    if last_practiced_at is None:
        return round(p, 4)

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if last_practiced_at.tzinfo is None:
        last_practiced_at = last_practiced_at.replace(tzinfo=timezone.utc)

    seconds_since = (now - last_practiced_at).total_seconds()
    days_since = max(0.0, seconds_since / 86400.0)

    r = retrievability(days_since, correct_count)
    p_init = settings.bkt_p_init

    if p > p_init:
        eff = p_init + (p - p_init) * r
    else:
        eff = p

    return round(float(eff), 4)


def is_due(retrievability_val: float, attempts_count: int) -> bool:
    """Determine whether a practiced topic is due for spaced review."""
    settings = get_settings()
    return int(attempts_count) > 0 and float(retrievability_val) < settings.review_due_below
