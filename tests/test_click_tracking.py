"""Tests that GET /{code} saves a click record."""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.main import app
from app.models import Click, Link
from tests import sample_agents

TARGET = "https://example.com/page"


def make_link(auth_client: TestClient, code: str = "mycode") -> str:
    """Create a short link and return its code."""
    response = auth_client.post("/links", json={"url": TARGET, "custom_code": code})
    assert response.status_code == 201
    return code


def get_clicks(db_session: Session) -> list[Click]:
    """All saved clicks, oldest first."""
    return list(db_session.scalars(select(Click).order_by(Click.id)))


# --- device type from the User-Agent ---------------------------------------


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        (sample_agents.IPHONE, "mobile"),
        (sample_agents.ANDROID_PHONE, "mobile"),
        (sample_agents.IPAD, "tablet"),
        (sample_agents.WINDOWS_CHROME, "desktop"),
        (sample_agents.GOOGLEBOT, "bot"),
    ],
)
def test_click_saves_device_type(
    auth_client: TestClient, db_session: Session, user_agent: str, expected: str
) -> None:
    code = make_link(auth_client)

    auth_client.get(
        f"/{code}", headers={"User-Agent": user_agent}, follow_redirects=False
    )

    clicks = get_clicks(db_session)
    assert len(clicks) == 1
    assert clicks[0].device_type == expected


def test_empty_user_agent_is_saved_as_bot(
    auth_client: TestClient, db_session: Session
) -> None:
    code = make_link(auth_client)

    auth_client.get(f"/{code}", headers={"User-Agent": ""}, follow_redirects=False)

    assert get_clicks(db_session)[0].device_type == "bot"


# --- referrer --------------------------------------------------------------


def test_referrer_is_saved(auth_client: TestClient, db_session: Session) -> None:
    code = make_link(auth_client)

    auth_client.get(
        f"/{code}",
        headers={"Referer": "https://news.example.org/post"},
        follow_redirects=False,
    )

    assert get_clicks(db_session)[0].referrer == "https://news.example.org/post"


def test_missing_referrer_is_null(auth_client: TestClient, db_session: Session) -> None:
    code = make_link(auth_client)

    auth_client.get(f"/{code}", follow_redirects=False)

    assert get_clicks(db_session)[0].referrer is None


def test_empty_referrer_is_null(auth_client: TestClient, db_session: Session) -> None:
    code = make_link(auth_client)

    auth_client.get(f"/{code}", headers={"Referer": ""}, follow_redirects=False)

    assert get_clicks(db_session)[0].referrer is None


def test_very_long_referrer_is_cut(
    auth_client: TestClient, db_session: Session
) -> None:
    code = make_link(auth_client)

    auth_client.get(
        f"/{code}",
        headers={"Referer": "https://example.org/" + "a" * 3000},
        follow_redirects=False,
    )

    assert len(get_clicks(db_session)[0].referrer or "") == 2048


# --- which clicks are saved ------------------------------------------------


def test_click_belongs_to_the_right_link(
    auth_client: TestClient, db_session: Session
) -> None:
    make_link(auth_client, "firstone")
    second = make_link(auth_client, "secondone")

    auth_client.get(f"/{second}", follow_redirects=False)

    second_link = db_session.scalar(select(Link).where(Link.code == second))
    assert second_link is not None
    clicks = get_clicks(db_session)
    assert len(clicks) == 1
    assert clicks[0].link_id == second_link.id


def test_every_click_creates_a_new_record(
    auth_client: TestClient, db_session: Session
) -> None:
    code = make_link(auth_client)

    for _ in range(3):
        auth_client.get(f"/{code}", follow_redirects=False)

    assert len(get_clicks(db_session)) == 3


def test_click_has_a_time(auth_client: TestClient, db_session: Session) -> None:
    code = make_link(auth_client)

    auth_client.get(f"/{code}", follow_redirects=False)

    assert get_clicks(db_session)[0].clicked_at is not None


def test_unknown_code_saves_no_click(
    auth_client: TestClient, db_session: Session
) -> None:
    make_link(auth_client)

    response = auth_client.get("/doesnotexist", follow_redirects=False)

    assert response.status_code == 404
    assert get_clicks(db_session) == []


# --- safety ----------------------------------------------------------------


def test_redirect_still_works_when_saving_the_click_fails(
    auth_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    code = make_link(auth_client)

    def broken_session_factory() -> Session:
        raise RuntimeError("database is down")

    app.dependency_overrides[get_session_factory] = lambda: broken_session_factory

    with caplog.at_level(logging.ERROR):
        response = auth_client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == TARGET
    assert "Could not save click" in caplog.text
