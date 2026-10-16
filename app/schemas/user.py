"""Request and response models for users."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Data the client sends to register."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        """Store emails in lowercase, so A@x.com and a@x.com are the same user."""
        return value.lower()


class UserRead(BaseModel):
    """Data the API returns about a user. It never has the password or hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime
