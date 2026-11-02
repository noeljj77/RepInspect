import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models import User


class EmailAlreadyRegistered(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def create_user(db: Session, *, email: str, display_name: str, password: str) -> User:
    user = User(
        email=normalize_email(email),
        display_name=display_name,
        password_hash=hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint is the real guard. Checking first and inserting
        # later would race when two requests register the same email at once.
        db.rollback()
        raise EmailAlreadyRegistered from None
    return user


def authenticate(db: Session, *, email: str, password: str) -> User | None:
    """Return the user if the credentials are right, otherwise None."""
    user = get_by_email(db, email)
    if user is None:
        verify_password(DUMMY_PASSWORD_HASH, password)  # keep timing similar
        return None
    if not verify_password(user.password_hash, password):
        return None

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    return user
