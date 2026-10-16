"""Business logic for users: register, check credentials, find by id."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.security import DUMMY_HASH, hash_password, verify_password


class EmailAlreadyRegisteredError(Exception):
    """A user with this email already exists."""


class InvalidCredentialsError(Exception):
    """The email or the password is wrong. We never say which one."""


def normalize_email(email: str) -> str:
    """Lowercase and trim an email, the same way registration does."""
    return email.strip().lower()


def register_user(db: Session, email: str, password: str) -> User:
    """Create a user. The unique index on email decides if it is taken."""
    user = User(email=normalize_email(email), password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailAlreadyRegisteredError(email) from None
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Return the user if the email and password match, else raise."""
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        # Do the same work as a real check, so timing does not reveal
        # which emails are registered.
        verify_password(password, DUMMY_HASH)
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Find a user by id, or return None."""
    return db.get(User, user_id)
