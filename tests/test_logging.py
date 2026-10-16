"""Tests for the JSON log lines and the request id."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.logging_config import JsonFormatter


def request_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "app.request"]


def test_every_request_writes_one_line_with_path_status_and_duration(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="app.request"):
        response = client.get("/nosuchcode")

    (record,) = request_records(caplog)
    assert record.method == "GET"
    assert record.path == "/nosuchcode"
    assert record.status == 404
    assert record.duration_ms >= 0
    assert record.request_id == response.headers["x-request-id"]


def test_the_query_string_is_not_logged(
    auth_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="app.request"):
        auth_client.get("/links/abc/stats?days=7&token=super-secret")

    text = " ".join(str(vars(r)) for r in caplog.records)
    assert "super-secret" not in text
    assert request_records(caplog)[0].path == "/links/abc/stats"


def test_tokens_and_passwords_are_not_logged(
    client: TestClient, user: object, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("DEBUG"):
        client.post(
            "/auth/login",
            data={"username": "a@example.com", "password": "very-secret-pw"},
            headers={"Authorization": "Bearer secret-token-value"},
        )

    text = " ".join(str(vars(r)) for r in caplog.records)
    assert "very-secret-pw" not in text
    assert "secret-token-value" not in text


def test_health_checks_are_only_logged_at_debug_level(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="app.request"):
        client.get("/health")
    assert request_records(caplog) == []

    with caplog.at_level("DEBUG", logger="app.request"):
        client.get("/health")
    assert len(request_records(caplog)) == 1


def test_a_safe_incoming_request_id_is_kept(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-123"})

    assert response.headers["x-request-id"] == "trace-123"


@pytest.mark.parametrize("bad", ["bad id with spaces", "x" * 65, "a\tb", "<script>"])
def test_an_unsafe_incoming_request_id_is_replaced(
    client: TestClient, bad: str
) -> None:
    response = client.get("/health", headers={"X-Request-ID": bad})

    assert response.headers["x-request-id"] != bad
    assert len(response.headers["x-request-id"]) == 32


def test_a_crash_is_logged_with_status_500(caplog: pytest.LogCaptureFixture) -> None:
    from app.main import app

    @app.get("/boom-log-test-only")
    def boom() -> None:
        raise RuntimeError("x")

    app.router.routes.insert(0, app.router.routes.pop())
    try:
        with caplog.at_level("INFO", logger="app.request"):
            TestClient(app, raise_server_exceptions=False).get("/boom-log-test-only")
    finally:
        app.router.routes.pop(0)

    assert request_records(caplog)[0].status == 500


def test_json_formatter_writes_one_json_object() -> None:
    record = logging.LogRecord(
        "app.request", logging.INFO, "f.py", 1, "request", None, None
    )
    record.method = "GET"
    record.status = 200

    data = json.loads(JsonFormatter().format(record))

    assert data["message"] == "request"
    assert data["level"] == "INFO"
    assert data["method"] == "GET"
    assert data["status"] == 200
    assert "request_id" not in data  # empty fields are left out
    assert data["time"].endswith("+00:00")


def test_json_formatter_includes_the_exception() -> None:
    try:
        raise ValueError("bad")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "app.x", logging.ERROR, "f.py", 1, "failed", None, sys.exc_info()
        )

    data = json.loads(JsonFormatter().format(record))

    assert "ValueError: bad" in data["exception"]
