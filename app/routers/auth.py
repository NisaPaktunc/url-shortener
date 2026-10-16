"""Endpoints for registering and logging in."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import security
from app.database import get_db
from app.rate_limit import limiter, login_limit
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """Create a new account."""
    try:
        user = user_service.register_user(db, payload.email, payload.password)
    except user_service.EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered.",
        ) from None
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
@limiter.limit(login_limit)
def login(
    request: Request,  # slowapi needs the request to find the client
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    """Log in and get a token.

    This is a form (not JSON) so the Authorize button in /docs works.
    Put the email in the "username" field. Limited per client IP address
    (5 per minute by default), so passwords cannot be guessed quickly.
    """
    try:
        user = user_service.authenticate_user(db, form.username, form.password)
    except user_service.InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return Token(access_token=security.create_access_token(user.id))
