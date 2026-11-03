import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import LoginLimits
from app.core.security import decode_token
from app.db.session import get_db
from app.models import RepositoryAnalysis, SavedRepository, User
from app.services import library, repositories, sessions, users

_NOT_AUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the logged-in user from the session cookie, or raise 401.

    Add this as a dependency to any route that needs a logged-in user. Every
    query for user-owned data must then filter by the returned user's id.
    """
    token = request.cookies.get(get_settings().session_cookie_name)
    claims = decode_token(token) if token else None
    if claims is None or sessions.is_revoked(db, claims.jti):
        raise _NOT_AUTHENTICATED
    user = users.get_by_id(db, claims.user_id)
    if user is None:
        raise _NOT_AUTHENTICATED
    return user


def get_login_limits(request: Request) -> LoginLimits:
    return request.app.state.login_limits


def get_owned_repository(
    repository_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedRepository:
    """The library entry from the URL, only if it belongs to the logged-in user.

    Someone else's repository gets the same 404 as one that does not exist, so the
    API never confirms that another user's repository id is real.
    """
    repository = repositories.get_owned(db, user.id, repository_id)
    if repository is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repository


def get_completed_analysis(
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> RepositoryAnalysis:
    """The newest analysis that finished successfully.

    While a refresh runs (or after one fails) this is still the previous version, so the
    files, explanations and chat stay usable until the new version is complete.
    """
    analysis = library.latest_completed(db, repository.id)
    if analysis is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="The analysis has not finished yet")
    return analysis
