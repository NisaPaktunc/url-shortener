"""Small helpers shared by the models."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    """Current time in UTC. Used as the default for created_at columns."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """A DateTime column that always gives back timezone-aware UTC values.

    SQLite does not store time zones, so a plain DateTime comes back without
    one. The API would then print some times with "Z" and some without, and a
    browser reads a time without "Z" as local time. This type fixes it:

    - saving: a time with another time zone is converted to UTC, and a time
      without a time zone is refused (we cannot know what it means)
    - loading: the time always comes back as UTC
    """

    impl = DateTime
    cache_ok = True

    def __init__(self) -> None:
        super().__init__(timezone=True)

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Use a timezone-aware datetime (for example UTC).")
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
