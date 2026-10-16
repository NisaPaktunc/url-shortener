"""Tests for how the models save and load times."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.models import Link, User
from tests.helpers import make_link


def test_times_come_back_as_utc_with_a_time_zone(
    db_session: Session, user: User
) -> None:
    created = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    link = make_link(db_session, user.id, "tz1", created_at=created)

    db_session.expire_all()  # forget the objects, so the next read goes to the database
    loaded = db_session.get(Link, link.id)

    assert loaded is not None
    assert loaded.created_at == created
    assert loaded.created_at.utcoffset() == timedelta(0)


def test_times_in_other_time_zones_are_saved_as_utc(
    db_session: Session, user: User
) -> None:
    istanbul = timezone(timedelta(hours=3))
    link = make_link(
        db_session,
        user.id,
        "tz2",
        created_at=datetime(2026, 1, 2, 3, 0, 0, tzinfo=istanbul),
    )

    db_session.expire_all()
    loaded = db_session.get(Link, link.id)

    assert loaded is not None
    assert loaded.created_at == datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
    assert loaded.created_at.utcoffset() == timedelta(0)


def test_times_without_a_time_zone_are_refused(db_session: Session, user: User) -> None:
    with pytest.raises(StatementError, match="timezone-aware"):
        make_link(db_session, user.id, "tz3", created_at=datetime(2026, 1, 2))
