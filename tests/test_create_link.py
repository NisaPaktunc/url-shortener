"""Tests for POST /links."""

import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app.services import link_service

VALID_URL = "https://example.com/some/page?x=1"


def create(auth_client: TestClient, **payload: str) -> httpx.Response:
    """Send POST /links with the given JSON fields."""
    return auth_client.post("/links", json=payload)


# --- valid input -----------------------------------------------------------


def test_create_link_returns_201_and_link_data(auth_client: TestClient) -> None:
    response = create(auth_client, url=VALID_URL)

    assert response.status_code == 201
    body = response.json()
    assert body["target_url"] == VALID_URL
    assert body["short_url"].endswith(f"/{body['code']}")
    assert body["created_at"]


def test_generated_code_is_7_characters_base62(auth_client: TestClient) -> None:
    code = create(auth_client, url=VALID_URL).json()["code"]

    assert re.fullmatch(r"[A-Za-z0-9]{7}", code)


@pytest.mark.parametrize("url", ["http://example.com/a", "https://example.com/a"])
def test_http_and_https_urls_are_accepted(auth_client: TestClient, url: str) -> None:
    assert create(auth_client, url=url).status_code == 201


def test_same_url_twice_gives_two_different_codes(auth_client: TestClient) -> None:
    first = create(auth_client, url=VALID_URL).json()["code"]
    second = create(auth_client, url=VALID_URL).json()["code"]

    assert first != second


# --- invalid URLs ----------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "example.com",
        "ftp://example.com/file.txt",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://",
        "",
    ],
)
def test_invalid_url_returns_422(auth_client: TestClient, url: str) -> None:
    assert create(auth_client, url=url).status_code == 422


def test_missing_url_returns_422(auth_client: TestClient) -> None:
    assert auth_client.post("/links", json={}).status_code == 422


# --- custom codes ----------------------------------------------------------


def test_custom_code_is_used(auth_client: TestClient) -> None:
    response = create(auth_client, url=VALID_URL, custom_code="mycode")

    assert response.status_code == 201
    assert response.json()["code"] == "mycode"
    assert response.json()["short_url"].endswith("/mycode")


def test_taken_custom_code_returns_409(auth_client: TestClient) -> None:
    create(auth_client, url=VALID_URL, custom_code="taken1")

    response = create(
        auth_client, url="https://other.example.com", custom_code="taken1"
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "code",
    [
        "ab",  # too short
        "a" * 33,  # too long
        "has space",
        "bad-code",
        "tür123",  # not plain letters and digits
        "health",  # reserved
        "Docs",  # reserved, in any letter case
    ],
)
def test_invalid_custom_code_returns_422(auth_client: TestClient, code: str) -> None:
    assert create(auth_client, url=VALID_URL, custom_code=code).status_code == 422


# --- collisions of random codes --------------------------------------------


def test_random_code_collision_is_retried(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    create(auth_client, url=VALID_URL, custom_code="abc1234")
    codes = iter(["abc1234", "abc1234", "zzz9999"])  # two collisions, then free
    monkeypatch.setattr(link_service, "generate_code", lambda: next(codes))

    response = create(auth_client, url="https://other.example.com")

    assert response.status_code == 201
    assert response.json()["code"] == "zzz9999"


def test_returns_503_when_every_attempt_collides(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    create(auth_client, url=VALID_URL, custom_code="abc1234")
    monkeypatch.setattr(link_service, "generate_code", lambda: "abc1234")

    response = create(auth_client, url="https://other.example.com")

    assert response.status_code == 503
