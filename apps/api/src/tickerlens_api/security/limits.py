from __future__ import annotations

from starlette.requests import Request

from tickerlens_api.security.rate_limit import rate_limit_or_429
from tickerlens_api.security.request_actor import actor_key


def rate_limit_request(*, request: Request, prefix: str, limit: int, window_s: int) -> None:
    """
    Convenience wrapper that rate limits by authenticated user_id if present,
    otherwise by client IP.
    """

    rate_limit_or_429(key=f"{prefix}:{actor_key(request)}", limit=limit, window_s=window_s)

