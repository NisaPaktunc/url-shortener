"""Password hashing and login tokens (JWT).

This file has no HTTP code. It only knows how to hash passwords and
how to make and read tokens.
"""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

ALGORITHM = "HS256"

_password_hasher = PasswordHasher()

# Hash of a throwaway password. When a login uses an unknown email we still
# check against this hash, so the answer takes the same time either way.
DUMMY_HASH = _password_hasher.hash("this-is-not-a-real-password")


def hash_password(password: str) -> str:
    """Turn a password into an Argon2 hash (with a random salt inside)."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against a stored hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, expires_in: timedelta | None = None) -> str:
    """Make a signed token that says "this is user <id>" until it expires."""
    now = datetime.now(UTC)
    lifetime = expires_in or timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id inside a token, or None if it is bad or expired.

    We always pass the allowed algorithms. Without that, an attacker could
    choose a weaker one (like "none") in the token header.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
