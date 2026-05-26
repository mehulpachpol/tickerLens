from __future__ import annotations

from starlette.requests import Request
from sqlalchemy.orm import Session

from tickerlens_api.db.models import AuditLog


def log_audit(
    db: Session,
    *,
    action: str,
    request: Request,
    user_id: str | None,
    status_code: int | None = None,
    details: dict | None = None,
) -> None:
    """
    Best-effort audit logging.

    Avoid raising from this path; audit should not take down the request.
    """

    try:
        request_id = getattr(request.state, "request_id", None)
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")

        row = AuditLog(
            user_id=user_id,
            action=action,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            request_id=request_id,
            ip=ip,
            user_agent=ua,
            details=details,
        )
        db.add(row)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

