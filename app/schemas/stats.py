"""Response models for the statistics endpoints."""

import datetime as dt

from pydantic import BaseModel


class LinkSummary(BaseModel):
    """One row of the user's link list."""

    code: str
    short_url: str
    target_url: str
    created_at: dt.datetime
    total_clicks: int  # all clicks since the link was created


class DailyClicks(BaseModel):
    """The number of clicks on one day (UTC)."""

    date: dt.date
    clicks: int


class DeviceBreakdown(BaseModel):
    """Clicks per device type. Every type is always present, even with 0."""

    mobile: int
    desktop: int
    tablet: int
    bot: int


class ReferrerCount(BaseModel):
    """Clicks that came from one referrer."""

    referrer: str
    clicks: int


class LinkStatsRead(BaseModel):
    """Statistics of one link for the last `days` days (today included)."""

    code: str
    days: int
    total_clicks: int  # only inside the chosen days, same as the sum of `daily`
    daily: list[DailyClicks]  # one entry per day, days without clicks have 0
    devices: DeviceBreakdown
    top_referrers: list[ReferrerCount]  # at most 5, clicks without referrer excluded
