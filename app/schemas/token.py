"""Response model for login."""

from pydantic import BaseModel


class Token(BaseModel):
    """The login token the client must send in the Authorization header."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105 (a name, not a password)
