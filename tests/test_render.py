"""Tests for render.yaml. Render cannot be reached from here, so we read the file."""

from pathlib import Path

import pytest

from app.config import Settings

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINT = yaml.safe_load((ROOT / "render.yaml").read_text("utf-8"))
SERVICE = BLUEPRINT["services"][0]
ENV = {item["key"]: item for item in SERVICE["envVars"]}

# Variables that are not settings of this app. uvicorn reads this one itself.
NOT_APP_SETTINGS = {"FORWARDED_ALLOW_IPS"}


def test_it_has_one_docker_web_service_and_one_database() -> None:
    assert len(BLUEPRINT["services"]) == 1
    assert len(BLUEPRINT["databases"]) == 1
    assert SERVICE["type"] == "web"
    assert SERVICE["runtime"] == "docker"
    assert (ROOT / SERVICE["dockerfilePath"]).is_file()


def test_the_health_check_is_the_health_endpoint() -> None:
    assert SERVICE["healthCheckPath"] == "/health"


def test_database_url_comes_from_the_database_in_the_file() -> None:
    source = ENV["DATABASE_URL"]["fromDatabase"]
    names = [database["name"] for database in BLUEPRINT["databases"]]

    assert source["name"] in names
    assert source["property"] == "connectionString"


def test_service_and_database_are_in_the_same_region() -> None:
    assert SERVICE["region"] == BLUEPRINT["databases"][0]["region"]


def test_secret_key_is_generated_by_render_and_not_written_in_the_file() -> None:
    assert ENV["SECRET_KEY"] == {"key": "SECRET_KEY", "generateValue": True}


def test_no_value_in_the_file_looks_like_a_password() -> None:
    text = (ROOT / "render.yaml").read_text("utf-8")

    assert "postgres://" not in text
    assert "postgresql://" not in text
    assert "password" not in text.lower().replace("fromdatabase", "")


def test_every_variable_is_a_real_setting_of_the_app() -> None:
    fields = {name.upper() for name in Settings.model_fields}

    unknown = set(ENV) - fields - NOT_APP_SETTINGS
    assert not unknown, f"Not settings of the app: {sorted(unknown)}"


def test_the_values_are_accepted_by_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, item in ENV.items():
        if "value" in item:
            monkeypatch.setenv(key, str(item["value"]))
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")

    settings = Settings()

    assert settings.rate_limit_enabled is True
    assert settings.login_rate_limit == "5/minute"


def test_the_container_listens_on_the_port_render_gives() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text("utf-8")

    assert "${PORT:-8000}" in dockerfile
