"""Tests for settings, mainly the database URL that hosting services give."""

import pytest

from app.config import Settings, normalize_database_url


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        (
            "postgresql://u:p@host/db?sslmode=require",
            "postgresql+psycopg://u:p@host/db?sslmode=require",
        ),
        # These stay as they are:
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///./shortener.db", "sqlite:///./shortener.db"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_normalize_database_url(given: str, expected: str) -> None:
    assert normalize_database_url(given) == expected


def test_settings_fix_the_url_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@dpg-abc/shortener")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)

    assert Settings().database_url == "postgresql+psycopg://u:p@dpg-abc/shortener"


def test_the_fixed_url_can_be_opened_by_sqlalchemy() -> None:
    from sqlalchemy.engine import make_url

    url = make_url(normalize_database_url("postgres://u:p@host/db"))

    assert url.drivername == "postgresql+psycopg"
    assert url.get_dialect().driver == "psycopg"
