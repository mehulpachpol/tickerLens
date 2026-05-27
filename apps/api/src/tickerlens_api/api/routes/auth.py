from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from tickerlens_api.auth.dependencies import get_current_user_optional
from tickerlens_api.auth.schemas import LoginRequest, LoginResponse, MeResponse, RegisterRequest, UserOut
from tickerlens_api.auth.service import authenticate_user, bootstrap_admin, create_session, create_user, revoke_session
from tickerlens_api.audit.service import log_audit
from tickerlens_api.db.session import get_db
from tickerlens_api.security.rate_limit import rate_limit_or_429
from tickerlens_api.security.request_actor import get_client_ip
from tickerlens_api.settings import settings


router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(u) -> UserOut:
    return UserOut(
        user_id=u.user_id,
        email=u.email,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at,
    )


@router.post("/register", response_model=LoginResponse)
def register(req: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth is disabled")
    if not settings.auth_allow_register:
        raise HTTPException(status_code=403, detail="Registration disabled")

    ip = get_client_ip(request)
    rate_limit_or_429(key=f"auth:register:{ip}", limit=5, window_s=60)

    u = create_user(db, email=req.email, password=req.password, role="user")
    token, _session = create_session(
        db,
        user_id=u.user_id,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=token,
        httponly=True,
        secure=bool(settings.auth_cookie_secure),
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
        max_age=int(settings.auth_session_ttl_hours) * 3600,
    )
    log_audit(db, action="auth.register", request=request, user_id=u.user_id, status_code=200)
    return LoginResponse(user=_user_out(u))


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth is disabled")

    ip = get_client_ip(request)
    rate_limit_or_429(key=f"auth:login:{ip}", limit=10, window_s=60)

    u = authenticate_user(db, email=req.email, password=req.password)
    if not u:
        log_audit(db, action="auth.login_failed", request=request, user_id=None, status_code=401, details={"email": req.email})
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, _session = create_session(
        db,
        user_id=u.user_id,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )

    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=token,
        httponly=True,
        secure=bool(settings.auth_cookie_secure),
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
        max_age=int(settings.auth_session_ttl_hours) * 3600,
    )
    log_audit(db, action="auth.login", request=request, user_id=u.user_id, status_code=200)
    return LoginResponse(user=_user_out(u))


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    if not settings.auth_enabled:
        return {"ok": True}

    # Try to revoke if cookie present.
    try:
        token = request.cookies.get(settings.auth_session_cookie_name) if request else None
        if token:
            revoke_session(db, token=token)
    except Exception:
        # Best-effort; cookie will still be cleared client-side.
        pass

    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        path="/",
        domain=settings.auth_cookie_domain,
    )
    log_audit(db, action="auth.logout", request=request, user_id=getattr(user, "user_id", None), status_code=200)
    return {"ok": True, "user_id": getattr(user, "user_id", None)}


@router.get("/me", response_model=MeResponse)
def me(user=Depends(get_current_user_optional), db: Session = Depends(get_db)) -> MeResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth is disabled")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return MeResponse(user=_user_out(user))


@router.post("/bootstrap")
def bootstrap(db: Session = Depends(get_db)) -> dict:
    """
    Manual bootstrap hook (useful if you don't want to rely on startup hooks).
    """

    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth is disabled")

    u = bootstrap_admin(db)
    return {"ok": True, "admin_created": bool(u), "admin_email": u.email if u else None}
