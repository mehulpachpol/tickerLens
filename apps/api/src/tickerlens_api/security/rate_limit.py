from __future__ import annotations

import time

from fastapi import HTTPException

from tickerlens_api.settings import settings


def _redis_client():
    try:
        import redis  # type: ignore

        return redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None


_client = _redis_client()


def rate_limit_or_429(*, key: str, limit: int, window_s: int) -> None:
    """
    Fixed-window rate limiter backed by Redis.

    If Redis isn't available, acts as a no-op (dev-friendly).
    """

    if not _client:
        return

    now = int(time.time())
    window = now // max(1, window_s)
    k = f"rl:{key}:{window}"

    try:
        count = int(_client.incr(k))
        if count == 1:
            _client.expire(k, window_s)
        if count > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except HTTPException:
        raise
    except Exception:
        # Fail-open to avoid making Redis availability a hard dependency.
        return

