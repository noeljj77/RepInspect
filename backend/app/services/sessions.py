"""Logging out: tokens are stateless, so a logout is remembered in a small deny-list."""

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.security import TokenClaims
from app.models import RevokedToken


def revoke(db: Session, claims: TokenClaims) -> None:
    # Logging out twice with the same token is harmless.
    db.execute(
        insert(RevokedToken)
        .values(jti=claims.jti, expires_at=claims.expires_at)
        .on_conflict_do_nothing()
    )
    db.commit()


def is_revoked(db: Session, jti: str) -> bool:
    return db.get(RevokedToken, jti) is not None


def purge_expired(db: Session) -> int:
    result = db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(UTC)))
    db.commit()
    return result.rowcount
