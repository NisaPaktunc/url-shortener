"""Tests for the Alembic migrations.

Each test works on its own temporary SQLite file.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
APP_TABLES = {"users", "links", "clicks"}


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    """Alembic settings that point to a temporary database file."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'migrations.db'}")
    return config


def table_names(config: Config) -> set[str]:
    """The tables that exist in the database the config points to."""
    engine = create_engine(config.get_main_option("sqlalchemy.url") or "")
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_creates_all_tables(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")

    assert table_names(alembic_config) >= APP_TABLES


def test_migrations_match_the_models(alembic_config: Config) -> None:
    """Fails if a model was changed but no migration was made for it."""
    command.upgrade(alembic_config, "head")

    command.check(alembic_config)


def test_downgrade_removes_all_tables(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")

    command.downgrade(alembic_config, "base")

    assert table_names(alembic_config).isdisjoint(APP_TABLES)
