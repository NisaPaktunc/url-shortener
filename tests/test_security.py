"""Tests for password hashing and tokens, without any HTTP involved."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app import security
from app.config import settings

# --- passwords -------------------------------------------------------------


def test_hash_is_not_the_password() -> None:
    password_hash = security.hash_password("my-password-123")

    assert "my-password-123" not in password_hash
    assert password_hash.startswith("$argon2id$")


def test_same_password_gives_different_hashes() -> None:
    first = security.hash_password("my-password-123")
    second = security.hash_password("my-password-123")

    assert first != second  # each hash has its own random salt


def test_correct_password_is_accepted() -> None:
    password_hash = security.hash_password("my-password-123")

    assert security.verify_password("my-password-123", password_hash) is True


def test_wrong_password_is_rejected() -> None:
    password_hash = security.hash_password("my-password-123")

    assert security.verify_password("other-password", password_hash) is False


def test_broken_hash_is_rejected_without_crashing() -> None:
    assert security.verify_password("my-password-123", "not-a-hash") is False


# --- tokens ----------------------------------------------------------------


def test_token_gives_back_the_user_id() -> None:
    token = security.create_access_token(42)

    assert security.decode_access_token(token) == 42


def test_expired_token_is_rejected() -> None:
    token = security.create_access_token(42, expires_in=timedelta(seconds=-1))

    assert security.decode_access_token(token) is None


def test_changed_token_is_rejected() -> None:
    header, payload, signature = security.create_access_token(42).split(".")
    changed = f"{header}.{payload}.{signature[:-2]}xx"

    assert security.decode_access_token(changed) is None


def test_token_signed_with_another_key_is_rejected() -> None:
    token = jwt.encode(
        {"sub": "42", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "another-secret-key-that-is-long-enough-123",
        algorithm="HS256",
    )

    assert security.decode_access_token(token) is None


def test_token_without_signature_is_rejected() -> None:
    token = jwt.encode(
        {"sub": "42", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        None,
        algorithm="none",
    )

    assert security.decode_access_token(token) is None


def test_token_without_expiry_is_rejected() -> None:
    token = jwt.encode({"sub": "42"}, settings.secret_key, algorithm="HS256")

    assert security.decode_access_token(token) is None


@pytest.mark.parametrize("token", ["", "garbage", "a.b.c"])
def test_garbage_is_rejected(token: str) -> None:
    assert security.decode_access_token(token) is None
