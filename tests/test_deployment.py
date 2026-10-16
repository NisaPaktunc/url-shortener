"""Tests for the deployment files (Dockerfile, entrypoint, docker-compose).

The tests cannot start Docker, so they read the files and check the rules
that matter: no root user, migrations before the app, healthchecks, and no
secrets inside the files.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
ENTRYPOINT = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
DOCKERIGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()


def test_dockerfile_has_two_stages() -> None:
    stages = re.findall(r"^FROM .+ AS (\w+)$", DOCKERFILE, flags=re.MULTILINE)

    assert stages == ["builder", "runtime"]
    assert "COPY --from=builder" in DOCKERFILE


def test_dockerfile_does_not_run_as_root() -> None:
    last_user = re.findall(r"^USER (\S+)$", DOCKERFILE, flags=re.MULTILINE)[-1]

    assert last_user not in {"root", "0"}
    # USER must come after all the setup lines that need root.
    assert DOCKERFILE.rindex("USER ") > DOCKERFILE.rindex("RUN ")


def test_dockerfile_does_not_copy_secrets_or_the_database() -> None:
    copies = "\n".join(re.findall(r"^COPY .+$", DOCKERFILE, flags=re.MULTILINE))

    assert ".env" not in copies.replace(".env.example", "")
    assert ".db" not in copies


def test_entrypoint_migrates_before_it_starts_the_app() -> None:
    assert "set -eu" in ENTRYPOINT  # a failed migration stops the container
    assert ENTRYPOINT.index("alembic upgrade head") < ENTRYPOINT.index('exec "$@"')


def test_dockerfile_starts_the_entrypoint_script() -> None:
    assert 'ENTRYPOINT ["/entrypoint.sh"]' in DOCKERFILE
    assert "uvicorn" in DOCKERFILE


def test_compose_has_both_services_a_volume_and_healthchecks() -> None:
    assert re.search(r"^  db:$", COMPOSE, flags=re.MULTILINE)
    assert re.search(r"^  app:$", COMPOSE, flags=re.MULTILINE)
    assert COMPOSE.count("healthcheck:") == 2
    assert "pgdata:/var/lib/postgresql/data" in COMPOSE
    assert re.search(r"^volumes:\n  pgdata:", COMPOSE, flags=re.MULTILINE)
    assert "condition: service_healthy" in COMPOSE


def test_compose_takes_secrets_from_the_environment_and_requires_them() -> None:
    assert "${POSTGRES_PASSWORD:?" in COMPOSE
    assert "${SECRET_KEY:?" in COMPOSE
    # The only password in the file is a variable, never a real value.
    assert re.findall(r"PASSWORD: (.+)", COMPOSE) == [
        "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in your .env file}"
    ]


def test_dockerignore_keeps_secrets_and_databases_out_of_the_image() -> None:
    assert ".env" in DOCKERIGNORE
    assert "*.db" in DOCKERIGNORE


def test_database_url_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+psycopg://shortener:pw@db:5432/shortener"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SECRET_KEY", "k" * 40)

    assert Settings().database_url == url


def test_postgres_driver_is_installed() -> None:
    import psycopg  # noqa: F401  (the import is the test)


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_docker_compose_file_is_valid() -> None:
    env = {
        **os.environ,
        "SECRET_KEY": "k" * 40,
        "POSTGRES_PASSWORD": "abc123",
    }
    ok = subprocess.run(
        ["docker", "compose", "config", "-q"],  # noqa: S607
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stderr

    missing = {
        k: v for k, v in env.items() if k not in {"SECRET_KEY", "POSTGRES_PASSWORD"}
    }
    bad = subprocess.run(
        ["docker", "compose", "config", "-q"],  # noqa: S607
        cwd=ROOT,
        env=missing,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode != 0  # it refuses to start without the secrets
    assert "SECRET_KEY" in bad.stderr or "POSTGRES_PASSWORD" in bad.stderr
