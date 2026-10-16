"""Click statistics.

All counting is done by the database with SQL (COUNT and GROUP BY), not by
Python loops. Python only does two small jobs: it fills in the days that have
no clicks with 0, and it turns the rows into a result object.

Time ranges are calculated in UTC.
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.models.click import Click, DeviceType
from app.models.link import Link
from app.services.link_service import LinkNotFoundError

TOP_REFERRERS = 5


@dataclass(frozen=True)
class LinkStats:
    """Statistics of one link inside a time range."""

    code: str
    days: int
    total_clicks: int
    daily: list[tuple[dt.date, int]]
    devices: dict[str, int]
    top_referrers: list[tuple[str, int]]


# --- SQL queries -----------------------------------------------------------
# They are small functions that only build a query, so each one is easy to
# read, test and print.


def links_with_counts_query(owner_id: int) -> Select:
    """A user's links with the number of clicks of each, newest link first.

    LEFT JOIN keeps links that have no clicks (their count is 0).
    """
    return (
        select(Link, func.count(Click.id).label("total_clicks"))
        .outerjoin(Click, Click.link_id == Link.id)
        .where(Link.owner_id == owner_id)
        .group_by(Link.id)
        .order_by(Link.created_at.desc(), Link.id.desc())
    )


def _in_range(
    link_id: int, start: dt.datetime, end: dt.datetime
) -> list[ColumnElement[bool]]:
    """Conditions for one link's clicks from `start` up to (not including) `end`."""
    return [
        Click.link_id == link_id,
        Click.clicked_at >= start,
        Click.clicked_at < end,
    ]


def daily_query(link_id: int, start: dt.datetime, end: dt.datetime) -> Select:
    """Clicks per day. Days without clicks are not in the result."""
    day = func.date(Click.clicked_at)
    return (
        select(day.label("day"), func.count(Click.id).label("clicks"))
        .where(*_in_range(link_id, start, end))
        .group_by(day)
        .order_by(day)
    )


def device_query(link_id: int, start: dt.datetime, end: dt.datetime) -> Select:
    """Clicks per device type."""
    return (
        select(Click.device_type, func.count(Click.id).label("clicks"))
        .where(*_in_range(link_id, start, end))
        .group_by(Click.device_type)
    )


def referrer_query(link_id: int, start: dt.datetime, end: dt.datetime) -> Select:
    """The referrers with the most clicks. Equal counts are sorted by name."""
    clicks = func.count(Click.id).label("clicks")
    return (
        select(Click.referrer, clicks)
        .where(*_in_range(link_id, start, end), Click.referrer.is_not(None))
        .group_by(Click.referrer)
        .order_by(clicks.desc(), Click.referrer)
        .limit(TOP_REFERRERS)
    )


def total_query(link_id: int, start: dt.datetime, end: dt.datetime) -> Select:
    """The total number of clicks."""
    return select(func.count(Click.id)).where(*_in_range(link_id, start, end))


# --- Public functions ------------------------------------------------------


def list_links_with_counts(db: Session, owner_id: int) -> list[tuple[Link, int]]:
    """Return the user's links, each with its all-time click count."""
    rows = db.execute(links_with_counts_query(owner_id)).all()
    return [(link, total_clicks) for link, total_clicks in rows]


def get_link_stats(
    db: Session,
    owner_id: int,
    code: str,
    days: int,
    now: dt.datetime | None = None,
) -> LinkStats:
    """Return the statistics of a link for the last `days` days, today included.

    Raises LinkNotFoundError when the link does not exist or belongs to
    someone else. The two cases look the same on purpose.
    `now` can be set in tests to get a fixed time.
    """
    link = _get_owned_link(db, owner_id, code)
    first_day, start, end = _day_range(days, now)

    daily_rows = db.execute(daily_query(link.id, start, end)).all()
    device_rows = db.execute(device_query(link.id, start, end)).all()
    referrer_rows = db.execute(referrer_query(link.id, start, end)).all()
    total = db.scalar(total_query(link.id, start, end)) or 0

    clicks_per_device = dict(device_rows)
    return LinkStats(
        code=link.code,
        days=days,
        total_clicks=total,
        daily=_fill_missing_days(first_day, days, daily_rows),
        devices={d.value: clicks_per_device.get(d.value, 0) for d in DeviceType},
        top_referrers=[(referrer, clicks) for referrer, clicks in referrer_rows],
    )


# --- Helpers ---------------------------------------------------------------


def _get_owned_link(db: Session, owner_id: int, code: str) -> Link:
    """Find a link by code, but only if this user owns it."""
    link = db.scalar(select(Link).where(Link.code == code, Link.owner_id == owner_id))
    if link is None:
        raise LinkNotFoundError(code)
    return link


def _day_range(
    days: int, now: dt.datetime | None
) -> tuple[dt.date, dt.datetime, dt.datetime]:
    """The first day, and the start and end of a range of `days` whole UTC days.

    The range ends with today, so `days=1` means today only.
    The end is the first moment of tomorrow, and it is not part of the range.
    """
    today = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC).date()
    first_day = today - dt.timedelta(days=days - 1)
    start = dt.datetime.combine(first_day, dt.time.min, tzinfo=dt.UTC)
    return first_day, start, start + dt.timedelta(days=days)


def _fill_missing_days(
    first_day: dt.date, days: int, rows: list[tuple[str | dt.date, int]]
) -> list[tuple[dt.date, int]]:
    """Make one entry per day, with 0 for the days that have no row.

    Making a list of dates is done here and not in SQL, because SQLite and
    Postgres write that differently.
    """
    counts = {dt.date.fromisoformat(str(day)): clicks for day, clicks in rows}
    all_days = [first_day + dt.timedelta(days=i) for i in range(days)]
    return [(day, counts.get(day, 0)) for day in all_days]
