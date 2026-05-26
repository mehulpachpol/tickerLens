from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from tickerlens_api.db.models import User
from tickerlens_api.db.session import get_db
from tickerlens_api.settings import settings

from .service import get_user_by_session_token


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.auth_session_cookie_name),
) -> User | None:
    if not settings.auth_enabled:
        return None
    if not session_token:
        return None
    u = get_user_by_session_token(db, token=session_token)
    if u:
        request.state.user_id = u.user_id
        request.state.user_role = u.role
    return u


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth is disabled")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_role(*required_roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in required_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _dep


def require_admin_if_auth_enabled(
    user: User | None = Depends(get_current_user_optional),
) -> User | None:
    """
    Useful for dev: when auth is disabled, don't block routes.
    When auth is enabled, require role=admin.
    """

    if not settings.auth_enabled:
        return None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def require_user_if_auth_enabled(
    user: User | None = Depends(get_current_user_optional),
) -> User | None:
    if not settings.auth_enabled:
        return None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
