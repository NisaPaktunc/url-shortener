"""The Click table: one row each time someone uses a short link."""

import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.utils import UTCDateTime, utc_now


class DeviceType(enum.StrEnum):
    """The kind of device that made the click."""

    MOBILE = "mobile"
    DESKTOP = "desktop"
    TABLET = "tablet"
    BOT = "bot"


class Click(Base):
    """One visit to a short link."""

    __tablename__ = "clicks"
    __table_args__ = (
        # Statistics always filter by one link and a time range,
        # so one index on both columns covers every query.
        Index("ix_clicks_link_id_clicked_at", "link_id", "clicked_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"))
    clicked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    device_type: Mapped[str] = mapped_column(String(10))
    referrer: Mapped[str | None] = mapped_column(String(2048), default=None)
