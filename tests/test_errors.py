"""Tests for the one error format and the global error handlers."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import app
from tests.sample_users import PASSWORD


def error_of(response) -> dict:
    """The "error" object of an answer. Fails if the format is not the standard."""
    body = response.json()
    assert set(body) == {"error"}
    return body["error"]


def test_404_for_unknown_code_uses_the_standard_format(client: TestClient) -> None:
    response = client.get("/nosuchcode")

    error = error_of(response)
    assert response.status_code == 404
    assert error["code"] == "not_found"
    assert error["message"] == "Short link not found."
    assert error["request_id"] == response.headers["x-request-id"]


def test_unknown_url_path_uses_the_standard_format(client: TestClient) -> None:
    response = client.get("/static/no/such/file.txt")

    assert response.status_code == 404
    assert error_of(response)["code"] == "not_found"


def test_wrong_method_gives_405_in_the_standard_format(client: TestClient) -> None:
    response = client.post("/health")

    assert response.status_code == 405
    assert error_of(response)["code"] == "method_not_allowed"


def test_401_keeps_the_www_authenticate_header(client: TestClient) -> None:
    response = client.get("/links")

    assert response.status_code == 401
    assert error_of(response)["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


def test_409_conflict(auth_client: TestClient) -> None:
    body = {"url": "https://example.com", "custom_code": "taken1"}
    auth_client.post("/links", json=body)

    response = auth_client.post("/links", json=body)

    assert response.status_code == 409
    assert error_of(response)["code"] == "conflict"


def test_422_lists_the_wrong_fields(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/links", json={"url": "ftp://example.com", "custom_code": "ab"}
    )

    error = error_of(response)
    assert response.status_code == 422
    assert error["code"] == "validation_error"
    fields = {item["field"] for item in error["details"]}
    assert fields == {"url", "custom_code"}
    assert all(item["message"] for item in error["details"])


def test_422_never_sends_the_input_back(client: TestClient) -> None:
    secret = "my-secret-password-value"
    response = client.post(
        "/auth/register", json={"email": "not-an-email", "password": secret}
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert "not-an-email" not in response.text


def test_422_for_a_query_parameter(auth_client: TestClient) -> None:
    response = auth_client.get("/links/abc/stats?days=0")

    assert response.status_code == 422
    assert error_of(response)["details"][0]["field"] == "days"


def test_unexpected_error_gives_500_without_details_and_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = APIRouter()

    @router.get("/boom-test-only")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    # Routes added at the end are behind /{code}, so add it at the front.
    app.router.routes.insert(0, router.routes[0])
    try:
        with caplog.at_level("ERROR"):
            response = TestClient(app, raise_server_exceptions=False).get(
                "/boom-test-only"
            )
    finally:
        app.router.routes.pop(0)

    error = error_of(response)
    assert response.status_code == 500
    assert error["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert response.headers["x-request-id"] == error["request_id"]
    assert any(
        r.exc_info and "secret internal detail" in str(r.exc_info[1])
        for r in caplog.records
    )


def test_successful_answers_are_not_wrapped(client: TestClient) -> None:
    response = client.get("/health")

    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


def test_login_422_does_not_echo_the_password(client: TestClient) -> None:
    response = client.post("/auth/login", data={"username": "a@b.co"})

    assert response.status_code == 422
    assert error_of(response)["details"][0]["field"] == "password"
    assert PASSWORD not in response.text
