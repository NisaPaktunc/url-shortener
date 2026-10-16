"""Tests for the statistics service, with a fixed "now" so every number is exact.

"Now" is 2026-10-11 15:30 UTC. Days are counted back from it, today included.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import Link, User
from app.services import link_service, stats_service
from tests.helpers import add_clicks, make_link

NOW = datetime(2026, 10, 11, 15, 30, tzinfo=UTC)
NEWS = "https://news.example.org/a"
BLOG = "https://blog.example.com"


def at(day: int, month: int = 10, hour: int = 12, minute: int = 0, second: int = 0):
    """A moment in 2026 (UTC)."""
    return datetime(2026, month, day, hour, minute, second, tzinfo=UTC)


@pytest.fixture
def alpha(db_session: Session, user: User) -> Link:
    """A link with 9 clicks. Only 6 of them are inside the last 30 days."""
    link = make_link(db_session, user.id, "alpha", created_at=at(1, month=8))
    add_clicks(
        db_session,
        link,
        [
            (at(11, hour=0), "mobile", NEWS),  # first second of today
            (at(11), "mobile", NEWS),
            (at(11, hour=23, minute=59, second=59), "desktop", None),  # last second
            (at(9), "tablet", BLOG),
            (at(9), "bot", None),
            (at(5), "desktop", NEWS),
            (at(12, hour=0), "mobile", "https://later.example.org"),  # tomorrow
            (at(1, month=9), "desktop", "https://old.example.org"),  # 40 days ago
            (at(1, month=9), "desktop", "https://old.example.org"),
        ],
    )
    return link


def stats(db: Session, user: User, code: str = "alpha", days: int = 30):
    """Shortcut for get_link_stats with the fixed "now"."""
    return stats_service.get_link_stats(db, user.id, code, days, now=NOW)


# --- total and days --------------------------------------------------------


def test_total_counts_only_clicks_inside_the_days(
    db_session: Session, user: User, alpha: Link
) -> None:
    assert stats(db_session, user).total_clicks == 6


def test_one_day_means_today_only(db_session: Session, user: User, alpha: Link) -> None:
    # Counts the first and the last second of today, not tomorrow's first second.
    assert stats(db_session, user, days=1).total_clicks == 3


def test_range_starts_exactly_n_days_back(
    db_session: Session, user: User, alpha: Link
) -> None:
    # The click on Oct 5 is 6 days before today, so it is inside 7 days only.
    assert stats(db_session, user, days=6).total_clicks == 5
    assert stats(db_session, user, days=7).total_clicks == 6


def test_longer_range_includes_older_clicks(
    db_session: Session, user: User, alpha: Link
) -> None:
    assert stats(db_session, user, days=60).total_clicks == 8


# --- daily -----------------------------------------------------------------


def test_daily_has_one_entry_for_every_day(
    db_session: Session, user: User, alpha: Link
) -> None:
    daily = stats(db_session, user).daily

    assert len(daily) == 30
    assert daily[0][0] == date(2026, 9, 12)
    assert daily[-1][0] == date(2026, 10, 11)
    assert [d for d, _ in daily] == [
        date(2026, 9, 12) + timedelta(days=i) for i in range(30)
    ]


def test_daily_counts_and_zero_days(
    db_session: Session, user: User, alpha: Link
) -> None:
    counts = dict(stats(db_session, user).daily)

    assert counts[date(2026, 10, 11)] == 3
    assert counts[date(2026, 10, 9)] == 2
    assert counts[date(2026, 10, 5)] == 1
    assert counts[date(2026, 10, 10)] == 0  # a day without clicks
    assert counts[date(2026, 9, 12)] == 0


def test_daily_adds_up_to_the_total(
    db_session: Session, user: User, alpha: Link
) -> None:
    result = stats(db_session, user)

    assert sum(clicks for _, clicks in result.daily) == result.total_clicks


# --- devices ---------------------------------------------------------------


def test_devices_are_counted(db_session: Session, user: User, alpha: Link) -> None:
    assert stats(db_session, user).devices == {
        "mobile": 2,
        "desktop": 2,
        "tablet": 1,
        "bot": 1,
    }


# --- referrers -------------------------------------------------------------


def test_top_referrers_are_sorted_and_skip_clicks_without_referrer(
    db_session: Session, user: User, alpha: Link
) -> None:
    # 2 of the 6 clicks have no referrer. They are not listed.
    assert stats(db_session, user).top_referrers == [(NEWS, 3), (BLOG, 1)]


def test_top_referrers_use_the_chosen_days(
    db_session: Session, user: User, alpha: Link
) -> None:
    assert stats(db_session, user, days=60).top_referrers == [
        (NEWS, 3),
        ("https://old.example.org", 2),
        (BLOG, 1),
    ]


def test_only_the_5_top_referrers_are_returned(db_session: Session, user: User) -> None:
    link = make_link(db_session, user.id, "beta")
    # referrer 1 has 1 click, referrer 2 has 2 clicks, ... referrer 7 has 7 clicks
    add_clicks(
        db_session,
        link,
        [
            (at(11), "desktop", f"https://site{n}.example.org")
            for n in range(1, 8)
            for _ in range(n)
        ],
    )

    top = stats(db_session, user, code="beta").top_referrers

    assert [clicks for _, clicks in top] == [7, 6, 5, 4, 3]
    assert top[0][0] == "https://site7.example.org"


def test_equal_referrer_counts_are_sorted_by_name(
    db_session: Session, user: User
) -> None:
    link = make_link(db_session, user.id, "ties")
    add_clicks(
        db_session,
        link,
        [
            (at(11), "desktop", "https://b.example.org"),
            (at(11), "desktop", "https://b.example.org"),
            (at(11), "desktop", "https://a.example.org"),
            (at(11), "desktop", "https://a.example.org"),
        ],
    )

    top = stats(db_session, user, code="ties").top_referrers

    assert top == [("https://a.example.org", 2), ("https://b.example.org", 2)]


# --- no data ---------------------------------------------------------------


def test_link_without_clicks_gives_zeros(db_session: Session, user: User) -> None:
    make_link(db_session, user.id, "empty")

    result = stats(db_session, user, code="empty")

    assert result.total_clicks == 0
    assert len(result.daily) == 30
    assert all(clicks == 0 for _, clicks in result.daily)
    assert result.devices == {"mobile": 0, "desktop": 0, "tablet": 0, "bot": 0}
    assert result.top_referrers == []


# --- who may see a link ----------------------------------------------------


def test_link_of_another_user_is_not_found(
    db_session: Session, user: User, other_user: User, alpha: Link
) -> None:
    with pytest.raises(link_service.LinkNotFoundError):
        stats_service.get_link_stats(db_session, other_user.id, "alpha", 30, now=NOW)


def test_unknown_code_is_not_found(db_session: Session, user: User) -> None:
    with pytest.raises(link_service.LinkNotFoundError):
        stats(db_session, user, code="nothere")


def test_link_without_owner_is_not_found(db_session: Session, user: User) -> None:
    make_link(db_session, None, "legacy")  # made before accounts existed

    with pytest.raises(link_service.LinkNotFoundError):
        stats(db_session, user, code="legacy")


# --- list of links ---------------------------------------------------------


def test_list_has_all_time_totals_newest_link_first(
    db_session: Session, user: User, other_user: User, alpha: Link
) -> None:
    make_link(db_session, user.id, "gamma", created_at=at(5))  # no clicks
    other = make_link(db_session, other_user.id, "omega", created_at=at(6))
    add_clicks(db_session, other, [(at(11), "desktop", None)])

    rows = stats_service.list_links_with_counts(db_session, user.id)

    # alpha counts all 9 clicks, also the ones outside the last 30 days.
    assert [(link.code, total) for link, total in rows] == [("gamma", 0), ("alpha", 9)]


def test_list_is_empty_for_a_user_without_links(
    db_session: Session, user: User
) -> None:
    assert stats_service.list_links_with_counts(db_session, user.id) == []
