"""Tests for scripts/seed.py (the demo data)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Click, Link, User
from app.services import stats_service
from scripts import seed as seed_script
from scripts.seed import (
    DEMO_EMAIL,
    DEMO_PASSWORD,
    DemoDataExistsError,
    seed,
)

NOW = datetime(2026, 10, 11, 15, 30, tzinfo=UTC)


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_seed_creates_user_links_and_a_realistic_number_of_clicks(
    db_session: Session,
) -> None:
    result = seed(db_session, now=NOW)

    assert (result.users, result.links) == (1, 5)
    assert 300 <= result.clicks <= 900
    assert count(db_session, User) == 1
    assert count(db_session, Link) == 5
    assert count(db_session, Click) == result.clicks


def test_demo_user_can_log_in(client: TestClient, db_session: Session) -> None:
    seed(db_session, now=NOW)

    response = client.post(
        "/auth/login", data={"username": DEMO_EMAIL, "password": DEMO_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_same_seed_gives_same_data_and_another_seed_does_not(
    db_session: Session,
) -> None:
    first = seed(db_session, rng_seed=1, now=NOW)
    again = seed(db_session, rng_seed=1, now=NOW, reset=True)
    other = seed(db_session, rng_seed=2, now=NOW, reset=True)

    assert first == again
    assert other.clicks != first.clicks


def test_reset_replaces_the_data_instead_of_adding_to_it(db_session: Session) -> None:
    seed(db_session, now=NOW)
    result = seed(db_session, now=NOW, reset=True)

    assert count(db_session, User) == 1
    assert count(db_session, Link) == 5
    assert count(db_session, Click) == result.clicks


def test_reset_keeps_the_data_of_other_users(
    db_session: Session, other_user: User
) -> None:
    other_link = Link(
        code="mine1", target_url="https://example.org", owner_id=other_user.id
    )
    db_session.add(other_link)
    db_session.commit()

    seed(db_session, now=NOW, reset=True)

    assert db_session.get(User, other_user.id) is not None
    assert db_session.scalar(select(Link).where(Link.code == "mine1")) is not None


def test_second_run_without_reset_is_refused(db_session: Session) -> None:
    seed(db_session, now=NOW)

    with pytest.raises(DemoDataExistsError):
        seed(db_session, now=NOW)
    assert count(db_session, User) == 1


def test_a_demo_code_used_by_someone_else_is_refused(
    db_session: Session, other_user: User
) -> None:
    db_session.add(
        Link(code="docs", target_url="https://x.org", owner_id=other_user.id)
    )
    db_session.commit()

    with pytest.raises(DemoDataExistsError, match="docs"):
        seed(db_session, now=NOW)


def test_quiet_link_has_no_clicks_and_others_have(db_session: Session) -> None:
    seed(db_session, now=NOW)
    user = db_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert user is not None

    totals = {
        link.code: total
        for link, total in stats_service.list_links_with_counts(db_session, user.id)
    }

    assert totals["quiet"] == 0
    assert all(
        totals[code] > 0 for code in ("launch", "docs", "newsletter", "portfolio")
    )


def test_no_click_is_in_the_future_or_before_its_link_exists(
    db_session: Session,
) -> None:
    seed(db_session, now=NOW)

    rows = db_session.execute(
        select(Click.clicked_at, Link.created_at).join(Link, Link.id == Click.link_id)
    ).all()

    assert rows
    for clicked_at, created_at in rows:
        assert created_at <= clicked_at <= NOW


def test_devices_and_referrers_look_realistic(db_session: Session) -> None:
    seed(db_session, now=NOW)

    devices = dict(
        db_session.execute(
            select(Click.device_type, func.count()).group_by(Click.device_type)
        ).all()
    )
    bots_with_referrer = db_session.scalar(
        select(func.count()).where(
            Click.device_type == "bot", Click.referrer.is_not(None)
        )
    )
    direct_visits = db_session.scalar(
        select(func.count()).where(Click.referrer.is_(None))
    )

    assert set(devices) == {"mobile", "desktop", "tablet", "bot"}
    assert devices["mobile"] > devices["desktop"] > devices["tablet"] > devices["bot"]
    assert bots_with_referrer == 0
    assert (direct_visits or 0) > 0


def test_stats_service_works_on_the_demo_data(db_session: Session) -> None:
    seed(db_session, now=NOW)
    user = db_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert user is not None

    stats = stats_service.get_link_stats(db_session, user.id, "launch", 30, now=NOW)

    assert stats.total_clicks > 0
    assert stats.total_clicks == sum(clicks for _, clicks in stats.daily)
    assert len(stats.daily) == 30
    assert len(stats.top_referrers) == 5


def test_command_line_refuses_a_database_that_is_not_sqlite(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        seed_script.settings,
        "database_url",
        "postgresql+psycopg://shortener:topsecret@db/shortener",
    )

    code = seed_script.main([])
    output = capsys.readouterr()

    assert code == 2
    assert "topsecret" not in output.out + output.err  # the password is hidden
    assert "Refusing" in output.err


def test_command_line_rejects_days_outside_the_allowed_range() -> None:
    with pytest.raises(SystemExit) as error:
        seed_script.main(["--days", "3"])

    assert error.value.code == 2
