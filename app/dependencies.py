"""Dependencies shared by several routers."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import security
from app.database import get_db
from app.models.user import User
from app.services import user_service

# Tells FastAPI to read "Authorization: Bearer <token>". A missing header
# gives a 401 automatically.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Return the logged-in user, or raise 401.

    Bad, expired and unknown-user tokens all get the same answer.
    """
    user_id = security.decode_access_token(token)
    user = user_service.get_user_by_id(db, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
