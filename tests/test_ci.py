"""Tests for the GitHub Actions workflow file (it cannot run here, so we read it)."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text("utf-8"))


def steps() -> list[dict]:
    return WORKFLOW["jobs"]["check"]["steps"]


def commands() -> list[str]:
    return [step["run"] for step in steps() if "run" in step]


def test_it_runs_on_push_and_on_pull_requests() -> None:
    triggers = WORKFLOW[True]  # YAML reads the key "on" as True

    assert "push" in triggers
    assert "pull_request" in triggers


def test_it_uses_python_312_with_a_pip_cache() -> None:
    setup = next(
        s for s in steps() if s.get("uses", "").startswith("actions/setup-python")
    )

    assert setup["with"]["python-version"] == "3.12"
    assert setup["with"]["cache"] == "pip"


def test_it_runs_ruff_and_pytest() -> None:
    assert "ruff check ." in commands()
    assert "ruff format --check ." in commands()
    assert "pytest" in commands()


def test_the_workflow_can_only_read_the_code() -> None:
    assert WORKFLOW["permissions"] == {"contents": "read"}


def test_the_readme_shows_the_ci_badge() -> None:
    readme = (ROOT / "README.md").read_text("utf-8")

    assert "actions/workflows/ci.yml/badge.svg" in readme
