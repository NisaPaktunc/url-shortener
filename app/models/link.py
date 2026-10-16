"""The Link table: one row per short link."""

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.utils import UTCDateTime, utc_now


class Link(Base):
    """A short code and the URL it points to."""

    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    # Empty only for links made before accounts existed. Every new link has an owner.
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
