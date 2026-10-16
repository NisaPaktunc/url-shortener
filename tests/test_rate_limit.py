"""Tests for rate limiting. They use the `rate_limits_on` fixture."""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.config import settings
from app.rate_limit import client_ip
from tests.sample_users import OWNER_EMAIL, PASSWORD


def login(client: TestClient, password: str = PASSWORD):
    return client.post(
        "/auth/login", data={"username": OWNER_EMAIL, "password": password}
    )


def create(client: TestClient, number: int):
    return client.post("/links", json={"url": f"https://example.com/{number}"})


@pytest.mark.usefixtures("rate_limits_on", "user")
def test_login_allows_5_per_minute_then_answers_429(client: TestClient) -> None:
    results = [login(client, "wrong-password-1").status_code for _ in range(5)]
    sixth = login(client, "wrong-password-1")

    assert results == [401] * 5
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "rate_limited"
    assert sixth.headers["retry-after"] == "60"


@pytest.mark.usefixtures("rate_limits_on", "user")
def test_a_correct_login_is_counted_too(client: TestClient) -> None:
    for _ in range(5):
        assert login(client).status_code == 200

    assert login(client).status_code == 429


@pytest.mark.usefixtures("rate_limits_on")
def test_create_link_allows_30_per_minute_then_answers_429(
    auth_client: TestClient,
) -> None:
    results = {create(auth_client, n).status_code for n in range(30)}
    thirty_first = create(auth_client, 31)

    assert results == {201}
    assert thirty_first.status_code == 429
    assert "retry-after" in thirty_first.headers


@pytest.mark.usefixtures("rate_limits_on")
def test_the_limit_comes_from_the_settings(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "create_link_rate_limit", "2/minute")

    codes = [create(auth_client, n).status_code for n in range(3)]

    assert codes == [201, 201, 429]


@pytest.mark.usefixtures("rate_limits_on", "user")
def test_other_endpoints_have_no_limit(client: TestClient) -> None:
    for _ in range(40):
        assert client.get("/health").status_code == 200
        assert client.get("/nosuchcode").status_code == 404


def test_limits_are_off_in_the_default_test_setup(
    client: TestClient, user: object
) -> None:
    assert all(login(client, "wrong-password-1").status_code == 401 for _ in range(8))


# ---- Which address is counted ------------------------------------------------


def request_with(*forwarded: str, client: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
    return Request(
        {"type": "http", "headers": headers, "client": (client, 5000)},
    )


def test_without_proxies_the_forwarded_header_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)

    assert client_ip(request_with("1.1.1.1")) == "10.0.0.1"


@pytest.mark.parametrize(
    ("hops", "header", "expected"),
    [
        (1, "9.9.9.9, 1.1.1.1", "1.1.1.1"),  # the left entry could be forged
        (1, "1.1.1.1", "1.1.1.1"),
        (2, "9.9.9.9, 1.1.1.1, 2.2.2.2", "1.1.1.1"),
        (2, "1.1.1.1", "10.0.0.1"),  # fewer entries than proxies: use the socket
        (1, "", "10.0.0.1"),
    ],
)
def test_behind_proxies_the_address_is_counted_from_the_right(
    monkeypatch: pytest.MonkeyPatch, hops: int, header: str, expected: str
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", hops)

    assert client_ip(request_with(header)) == expected


def test_several_forwarded_headers_are_read_as_one_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)

    assert client_ip(request_with("9.9.9.9", "1.1.1.1")) == "1.1.1.1"


@pytest.mark.usefixtures("rate_limits_on", "user")
def test_a_forged_forwarded_header_does_not_get_around_the_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)

    def attempt(forged: str, real: str) -> int:
        headers = {"X-Forwarded-For": f"{forged}, {real}"}
        return client.post(
            "/auth/login",
            data={"username": OWNER_EMAIL, "password": "wrong-password-1"},
            headers=headers,
        ).status_code

    forged_each_time = [attempt(f"198.51.100.{n}", "203.0.113.7") for n in range(6)]
    another_real_client = attempt("198.51.100.1", "203.0.113.8")

    assert forged_each_time == [401] * 5 + [429]
    assert another_real_client == 401  # a different real address has its own count
