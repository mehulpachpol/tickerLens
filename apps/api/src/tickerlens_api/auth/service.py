from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.auth.security import (
    hash_password,
    normalize_email,
    session_token,
    sha256_hex,
    verify_password,
)
from tickerlens_api.db.models import User, UserSession
from tickerlens_api.settings import settings


def get_user_by_email(db: Session, *, email: str) -> User | None:
    email_norm = normalize_email(email)
    return db.execute(select(User).where(User.email == email_norm).limit(1)).scalars().first()


def get_user(db: Session, *, user_id: str) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, *, email: str, password: str, role: str = "user") -> User:
    email_norm = normalize_email(email)
    if not email_norm or "@" not in email_norm:
        raise ValueError("Invalid email")

    existing = get_user_by_email(db, email=email_norm)
    if existing:
        raise ValueError("Email already registered")

    u = User(
        user_id=str(uuid.uuid4()),
        email=email_norm,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def authenticate_user(db: Session, *, email: str, password: str) -> User | None:
    u = get_user_by_email(db, email=email)
    if not u:
        return None
    if not u.is_active:
        return None
    if not verify_password(password=password, password_hash=u.password_hash):
        return None
    return u


def create_session(
    db: Session,
    *,
    user_id: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[str, UserSession]:
    token = session_token()
    token_sha = sha256_hex(token)
    now = dt.datetime.now(dt.timezone.utc)
    expires = now + dt.timedelta(hours=int(settings.auth_session_ttl_hours))

    s = UserSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        session_token_sha256=token_sha,
        expires_at=expires,
        revoked_at=None,
        last_seen_at=now,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return token, s


def revoke_session(db: Session, *, token: str) -> None:
    token_sha = sha256_hex(token)
    s = (
        db.execute(select(UserSession).where(UserSession.session_token_sha256 == token_sha).limit(1))
        .scalars()
        .first()
    )
    if not s:
        return
    if s.revoked_at is None:
        s.revoked_at = dt.datetime.now(dt.timezone.utc)
        db.commit()


def get_user_by_session_token(db: Session, *, token: str) -> User | None:
    token_sha = sha256_hex(token)
    now = dt.datetime.now(dt.timezone.utc)

    s = (
        db.execute(select(UserSession).where(UserSession.session_token_sha256 == token_sha).limit(1))
        .scalars()
        .first()
    )
    if not s:
        return None
    if s.revoked_at is not None:
        return None
    if s.expires_at <= now:
        return None

    # Touch last_seen for ops visibility (best-effort).
    try:
        s.last_seen_at = now
        db.commit()
    except Exception:
        db.rollback()

    u = get_user(db, user_id=s.user_id)
    if not u or not u.is_active:
        return None
    return u


def bootstrap_admin(db: Session) -> User | None:
    """
    Optional bootstrap for local dev/first deploy.

    If TICKERLENS_AUTH_BOOTSTRAP_ADMIN_EMAIL/PASSWORD are set, ensures that user exists with role=admin.
    """

    if not settings.auth_bootstrap_admin_email or not settings.auth_bootstrap_admin_password:
        return None

    email = normalize_email(settings.auth_bootstrap_admin_email)
    existing = get_user_by_email(db, email=email)
    if existing:
        if existing.role != "admin":
            existing.role = "admin"
            db.commit()
            db.refresh(existing)
        return existing

    return create_user(
        db,
        email=email,
        password=settings.auth_bootstrap_admin_password,
        role="admin",
    )

