import math
import random
from datetime import timedelta

from ..extensions import db
from ..models.password_reset import RateLimitEvent
from ..utils.helpers import utcnow

_RETENTION = timedelta(days=1)


def check_and_record(bucket: str, *rules: tuple[int, int]) -> int | None:
    """Apply every (limit, window_seconds) rule to `bucket`.

    Returns the seconds to wait if any rule is exceeded (nothing is recorded), otherwise
    records this request and returns None. Commits immediately so the hit counts even if
    the caller's work later fails.
    """
    now = utcnow()
    for limit, window in rules:
        recent = RateLimitEvent.query.filter(
            RateLimitEvent.bucket == bucket,
            RateLimitEvent.created_at > now - timedelta(seconds=window),
        )
        if recent.count() >= limit:
            oldest = recent.order_by(RateLimitEvent.created_at).first().created_at
            return max(1, math.ceil((oldest + timedelta(seconds=window) - now).total_seconds()))

    db.session.add(RateLimitEvent(bucket=bucket, created_at=now))
    if random.random() < 0.01:
        RateLimitEvent.query.filter(RateLimitEvent.created_at < now - _RETENTION).delete()
    db.session.commit()
    return None


def retry_message(seconds: int) -> str:
    if seconds < 60:
        return f"Too many requests. Try again in {seconds} seconds."
    minutes = math.ceil(seconds / 60)
    return f"Too many requests. Try again in {minutes} minute{'s' if minutes != 1 else ''}."
