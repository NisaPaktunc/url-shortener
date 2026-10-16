"""Tests for registration, login and login-protected endpoints."""

from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security
from app.models import Link, User
from tests.sample_users import EMAIL, PASSWORD


def register(
    client: TestClient, email: str = EMAIL, password: str = PASSWORD
) -> httpx.Response:
    """Send POST /auth/register."""
    return client.post("/auth/register", json={"email": email, "password": password})


def login(
    client: TestClient, email: str = EMAIL, password: str = PASSWORD
) -> httpx.Response:
    """Send POST /auth/login. It is a form, and the email goes in "username"."""
    return client.post("/auth/login", data={"username": email, "password": password})


def create_link(
    client: TestClient, headers: dict[str, str] | None = None
) -> httpx.Response:
    """Send POST /links, with optional headers."""
    return client.post("/links", json={"url": "https://example.com"}, headers=headers)


# --- register --------------------------------------------------------------


def test_register_returns_201_and_user_data(client: TestClient) -> None:
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == EMAIL
    assert isinstance(body["id"], int)
    assert body["created_at"]


def test_register_never_returns_password_or_hash(client: TestClient) -> None:
    body = register(client).json()

    assert "password" not in body
    assert "password_hash" not in body


def test_register_saves_email_in_lowercase(client: TestClient) -> None:
    response = register(client, email="Student@Example.COM")

    assert response.json()["email"] == "student@example.com"


def test_password_is_stored_as_argon2_hash(
    client: TestClient, db_session: Session
) -> None:
    register(client)

    user = db_session.scalar(select(User))

    assert user is not None
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2")


def test_duplicate_email_returns_409(client: TestClient) -> None:
    register(client)

    assert register(client).status_code == 409


def test_duplicate_email_ignores_letter_case(client: TestClient) -> None:
    register(client)

    assert register(client, email=EMAIL.upper()).status_code == 409


@pytest.mark.parametrize("email", ["not-an-email", "missing@", "@example.com", ""])
def test_invalid_email_returns_422(client: TestClient, email: str) -> None:
    assert register(client, email=email).status_code == 422


@pytest.mark.parametrize("password", ["short", "a" * 129, ""])
def test_invalid_password_returns_422(client: TestClient, password: str) -> None:
    assert register(client, password=password).status_code == 422


def test_register_without_fields_returns_422(client: TestClient) -> None:
    assert client.post("/auth/register", json={}).status_code == 422


# --- login -----------------------------------------------------------------


def test_login_returns_bearer_token(client: TestClient) -> None:
    register(client)

    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert security.decode_access_token(body["access_token"]) is not None


def test_token_belongs_to_the_user(client: TestClient) -> None:
    user_id = register(client).json()["id"]

    token = login(client).json()["access_token"]

    assert security.decode_access_token(token) == user_id


def test_login_ignores_email_letter_case(client: TestClient) -> None:
    register(client)

    assert login(client, email=EMAIL.upper()).status_code == 200


def test_wrong_password_returns_401(client: TestClient) -> None:
    register(client)

    response = login(client, password="wrong-password-123")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_unknown_email_returns_401_with_the_same_message(client: TestClient) -> None:
    register(client)

    wrong_password = login(client, password="wrong-password-123")
    unknown_email = login(client, email="nobody@example.com")

    assert unknown_email.status_code == 401
    # Only request_id differs between two answers, so compare code and message.
    assert unknown_email.json()["error"]["code"] == "unauthorized"
    assert (
        unknown_email.json()["error"]["message"]
        == (wrong_password.json()["error"]["message"])
    )


def test_login_without_fields_returns_422(client: TestClient) -> None:
    assert client.post("/auth/login", data={}).status_code == 422


# --- endpoints that need a login -------------------------------------------


def test_create_link_without_token_returns_401(client: TestClient) -> None:
    assert create_link(client).status_code == 401


@pytest.mark.parametrize("token", ["garbage", "a.b.c"])
def test_create_link_with_bad_token_returns_401(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}

    assert create_link(client, headers).status_code == 401


def test_create_link_with_expired_token_returns_401(
    client: TestClient, user: User
) -> None:
    token = security.create_access_token(user.id, expires_in=timedelta(minutes=-1))

    response = create_link(client, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_create_link_with_token_signed_by_another_key_returns_401(
    client: TestClient, user: User
) -> None:
    token = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "another-secret-key-that-is-long-enough-123",
        algorithm="HS256",
    )

    response = create_link(client, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_create_link_with_token_of_unknown_user_returns_401(
    client: TestClient,
) -> None:
    token = security.create_access_token(user_id=9999)

    response = create_link(client, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_link_gets_the_logged_in_user_as_owner(
    client: TestClient,
    db_session: Session,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    response = create_link(client, auth_headers)

    assert response.status_code == 201
    link = db_session.scalar(select(Link).where(Link.code == response.json()["code"]))
    assert link is not None
    assert link.owner_id == user.id


def test_register_login_and_create_link(client: TestClient) -> None:
    register(client)
    token = login(client).json()["access_token"]

    response = create_link(client, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
