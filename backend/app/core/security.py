"""Password hashing and login tokens."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

# argon2-cffi's defaults follow the RFC 9106 recommendations. The hash string
# it produces embeds the algorithm, parameters and a random salt, so we only
# store that one string per user.
_hasher = PasswordHasher()

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the stored hash uses weaker parameters than the current defaults."""
    return _hasher.check_needs_rehash(password_hash)


# Verified against when a login uses an unknown email, so that "no such user"
# takes as long as "wrong password" and response time doesn't reveal which
# emails are registered.
DUMMY_PASSWORD_HASH = _hasher.hash("not-a-real-password")


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        # A unique id per token, so one login can be revoked on logout (see services/sessions.py).
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    jti: str
    expires_at: datetime


def decode_token(token: str) -> TokenClaims | None:
    """Return the claims of a valid token, or None for anything invalid or expired."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            # Pinning the algorithm list blocks "alg: none" and key-confusion attacks.
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "jti"]},
        )
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            jti=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError):
        return None


def decode_access_token(token: str) -> uuid.UUID | None:
    """Return the user id from a valid token, or None for anything invalid or expired."""
    claims = decode_token(token)
    return claims.user_id if claims else None
