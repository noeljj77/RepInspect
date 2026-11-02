from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.services import users

_NOT_AUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the logged-in user from the session cookie, or raise 401.

    Add this as a dependency to any route that needs a logged-in user. Every
    query for user-owned data must then filter by the returned user's id.
    """
    token = request.cookies.get(get_settings().session_cookie_name)
    user_id = decode_access_token(token) if token else None
    user = users.get_by_id(db, user_id) if user_id else None
    if user is None:
        raise _NOT_AUTHENTICATED
    return user
