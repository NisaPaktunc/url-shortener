"""Tests for GET /{code}."""

from fastapi.testclient import TestClient

TARGET = "https://example.com/some/page?x=1"


def test_redirect_returns_302_to_target_url(auth_client: TestClient) -> None:
    code = auth_client.post("/links", json={"url": TARGET}).json()["code"]

    response = auth_client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == TARGET


def test_redirect_works_for_custom_code(auth_client: TestClient) -> None:
    auth_client.post("/links", json={"url": TARGET, "custom_code": "mycode"})

    response = auth_client.get("/mycode", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == TARGET


def test_unknown_code_returns_404(auth_client: TestClient) -> None:
    response = auth_client.get("/doesnotexist", follow_redirects=False)

    assert response.status_code == 404


def test_codes_are_case_sensitive(auth_client: TestClient) -> None:
    auth_client.post("/links", json={"url": TARGET, "custom_code": "AbCdEfG"})

    response = auth_client.get("/abcdefg", follow_redirects=False)

    assert response.status_code == 404


def test_redirect_route_does_not_hide_health(auth_client: TestClient) -> None:
    assert auth_client.get("/health").json() == {"status": "ok"}


def test_redirect_is_public_and_needs_no_token(
    auth_client: TestClient, client: TestClient
) -> None:
    auth_client.post("/links", json={"url": TARGET, "custom_code": "mycode"})

    response = client.get("/mycode", follow_redirects=False)  # not logged in

    assert response.status_code == 302
    assert response.headers["location"] == TARGET
