"""Tests for GET /links and GET /links/{code}/stats.

The router uses the real current time, so these tests put clicks at times
relative to now, and check sums and shapes. The exact day-by-day numbers are
tested in test_stats_service.py with a fixed time.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import DeviceType, Link, User
from app.schemas.stats import DeviceBreakdown
from tests.helpers import add_clicks, make_link

NEWS = "https://news.example.org/a"


@pytest.fixture
def alpha(db_session: Session, user: User) -> Link:
    """A link with 4 clicks. Only 3 of them are inside the last 30 days."""
    now = datetime.now(UTC)
    link = make_link(db_session, user.id, "alpha")
    add_clicks(
        db_session,
        link,
        [
            (now, "mobile", NEWS),
            (now - timedelta(days=1), "mobile", NEWS),
            (now - timedelta(days=2), "desktop", None),
            (now - timedelta(days=40), "bot", None),
        ],
    )
    return link


# --- GET /links ------------------------------------------------------------


def test_list_links_needs_a_login(client: TestClient) -> None:
    assert client.get("/links").status_code == 401


def test_list_links_is_empty_for_a_new_user(auth_client: TestClient) -> None:
    response = auth_client.get("/links")

    assert response.status_code == 200
    assert response.json() == []


def test_list_links_shows_only_own_links_with_click_totals(
    auth_client: TestClient, db_session: Session, other_user: User, alpha: Link
) -> None:
    make_link(db_session, None, "legacy")
    other = make_link(db_session, other_user.id, "omega")
    add_clicks(db_session, other, [(datetime.now(UTC), "desktop", None)])

    response = auth_client.get("/links")

    assert response.status_code == 200
    links = response.json()
    assert [link["code"] for link in links] == ["alpha"]
    assert links[0]["total_clicks"] == 4
    assert links[0]["short_url"].endswith("/alpha")
    assert links[0]["created_at"].endswith("Z")  # always UTC, so browsers read it right
    assert links[0]["target_url"] == "https://example.com/alpha"


def test_list_links_shows_newest_first_and_links_without_clicks(
    auth_client: TestClient, db_session: Session, user: User
) -> None:
    make_link(db_session, user.id, "older", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    make_link(db_session, user.id, "newer", created_at=datetime(2026, 2, 1, tzinfo=UTC))

    links = auth_client.get("/links").json()

    assert [(link["code"], link["total_clicks"]) for link in links] == [
        ("newer", 0),
        ("older", 0),
    ]


# --- GET /links/{code}/stats -----------------------------------------------


def test_stats_need_a_login(client: TestClient, alpha: Link) -> None:
    assert client.get("/links/alpha/stats").status_code == 401


def test_stats_of_own_link(auth_client: TestClient, alpha: Link) -> None:
    response = auth_client.get("/links/alpha/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "alpha"
    assert body["days"] == 30
    assert body["total_clicks"] == 3  # the click from 40 days ago is not counted
    assert len(body["daily"]) == 30
    assert sum(day["clicks"] for day in body["daily"]) == body["total_clicks"]
    assert body["devices"] == {"mobile": 2, "desktop": 1, "tablet": 0, "bot": 0}
    assert body["top_referrers"] == [{"referrer": NEWS, "clicks": 2}]


def test_days_parameter_sets_the_range(auth_client: TestClient, alpha: Link) -> None:
    body = auth_client.get("/links/alpha/stats", params={"days": 7}).json()

    assert body["days"] == 7
    assert len(body["daily"]) == 7
    assert body["total_clicks"] == 3


def test_longer_range_counts_older_clicks(auth_client: TestClient, alpha: Link) -> None:
    body = auth_client.get("/links/alpha/stats", params={"days": 90}).json()

    assert len(body["daily"]) == 90
    assert body["total_clicks"] == 4


def test_stats_of_a_link_without_clicks(
    auth_client: TestClient, db_session: Session, user: User
) -> None:
    make_link(db_session, user.id, "empty")

    body = auth_client.get("/links/empty/stats").json()

    assert body["total_clicks"] == 0
    assert all(day["clicks"] == 0 for day in body["daily"])
    assert body["devices"] == {"mobile": 0, "desktop": 0, "tablet": 0, "bot": 0}
    assert body["top_referrers"] == []


def test_link_of_another_user_returns_404(
    auth_client: TestClient, db_session: Session, other_user: User
) -> None:
    make_link(db_session, other_user.id, "theirs")

    response = auth_client.get("/links/theirs/stats")

    assert response.status_code == 404


def test_missing_link_gives_the_same_404_as_another_users_link(
    auth_client: TestClient, db_session: Session, other_user: User
) -> None:
    make_link(db_session, other_user.id, "theirs")

    theirs = auth_client.get("/links/theirs/stats")
    missing = auth_client.get("/links/doesnotexist/stats")

    assert missing.status_code == 404
    # Only request_id differs between two answers, so compare code and message.
    assert missing.json()["error"]["code"] == "not_found"
    assert missing.json()["error"]["message"] == theirs.json()["error"]["message"]


def test_link_without_owner_returns_404(
    auth_client: TestClient, db_session: Session
) -> None:
    make_link(db_session, None, "legacy")

    assert auth_client.get("/links/legacy/stats").status_code == 404


@pytest.mark.parametrize("days", ["0", "-5", "366", "abc", ""])
def test_invalid_days_returns_422(
    auth_client: TestClient, alpha: Link, days: str
) -> None:
    response = auth_client.get("/links/alpha/stats", params={"days": days})

    assert response.status_code == 422


def test_device_breakdown_has_every_device_type() -> None:
    assert set(DeviceBreakdown.model_fields) == {d.value for d in DeviceType}
