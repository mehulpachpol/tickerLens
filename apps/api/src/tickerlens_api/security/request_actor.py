from __future__ import annotations

from starlette.requests import Request


def get_client_ip(request: Request) -> str | None:
    """
    Best-effort client IP extraction.

    In production behind proxies/load balancers, prefer X-Forwarded-For.
    In local dev (docker compose), Request.client.host is typically enough.
    """

    try:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # XFF can be a comma-separated chain. The left-most is the original client.
            return xff.split(",")[0].strip() or None
    except Exception:
        pass

    try:
        return request.client.host if request.client else None
    except Exception:
        return None


def actor_key(request: Request) -> str:
    """
    Stable key for rate limiting / abuse controls.

    - If authenticated, use user_id from request.state (set by auth dependency)
    - Otherwise, fall back to IP (best-effort)
    """

    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    ip = get_client_ip(request) or "unknown"
    return f"ip:{ip}"

