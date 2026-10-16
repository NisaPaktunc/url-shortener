"""Request and response models for links."""

from datetime import datetime
from typing import Annotated

from pydantic import AnyUrl, BaseModel, Field, UrlConstraints, field_validator

# Words that are already used by the app's own routes. A short link with one
# of these codes would clash with a real page, so we do not allow them.
RESERVED_CODES = frozenset(
    {
        "health",
        "docs",
        "redoc",
        "openapi",
        "links",
        "dashboard",
        "stats",
        "static",
        "api",
        "auth",
    }
)

# Only http and https URLs can be shortened.
WebUrl = Annotated[
    AnyUrl, UrlConstraints(allowed_schemes=["http", "https"], max_length=2048)
]


class LinkCreate(BaseModel):
    """Data the client sends to create a short link."""

    url: WebUrl
    custom_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9]+$",
        description="Optional. Letters and digits only, 3 to 32 characters.",
    )

    @field_validator("custom_code")
    @classmethod
    def code_must_not_be_reserved(cls, value: str | None) -> str | None:
        """Reject codes that clash with the app's own routes."""
        if value is not None and value.lower() in RESERVED_CODES:
            raise ValueError("This code is reserved. Please choose another one.")
        return value


class LinkRead(BaseModel):
    """Data the API returns after a short link is created."""

    code: str
    short_url: str
    target_url: str
    created_at: datetime
