"""Database models. Import them here so SQLAlchemy knows every table."""

from app.models.click import Click, DeviceType
from app.models.link import Link
from app.models.user import User

__all__ = ["Click", "DeviceType", "Link", "User"]
