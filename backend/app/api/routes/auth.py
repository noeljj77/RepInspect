from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_login_limits
from app.core.config import get_settings
from app.core.rate_limit import LoginLimits, client_ip
from app.core.security import create_access_token, decode_token
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.services import sessions, users

router = APIRouter(prefix="/auth", tags=["auth"])

# Scoped to /api so the browser doesn't attach it to requests for the web app itself.
COOKIE_PATH = "/api"


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_access_token(user.id),
        max_age=settings.access_token_expire_minutes * 60,
        path=COOKIE_PATH,
        httponly=True,  # not readable from JavaScript, so XSS can't steal the token
        secure=settings.cookie_secure,
        samesite="lax",  # not sent on cross-site POSTs, which blocks CSRF
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> User:
    try:
        user = users.create_user(
            db, email=body.email, display_name=body.display_name, password=body.password
        )
    except users.EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    limits: LoginLimits = Depends(get_login_limits),
) -> User:
    email = users.normalize_email(body.email)
    ip = client_ip(request, trust_proxy_headers=get_settings().trust_proxy_headers)

    wait = max(limits.by_email.retry_after(email), limits.by_ip.retry_after(ip))
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {max(1, round(wait / 60))} minutes.",
            headers={"Retry-After": str(wait)},
        )

    user = users.authenticate(db, email=email, password=body.password)
    if user is None:
        limits.by_email.record_failure(email)
        limits.by_ip.record_failure(ip)
        # One message for both "unknown email" and "wrong password".
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    # Only the email counter is cleared: otherwise an attacker could reset the per-IP
    # count by logging in to an account of their own between guesses.
    limits.by_email.reset(email)
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    claims = decode_token(token) if token else None
    if claims is not None:
        # Clearing the cookie only affects this browser; this makes a copied token useless too.
        sessions.revoke(db, claims)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
