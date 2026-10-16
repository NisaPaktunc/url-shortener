"""Tests for the dashboard page and its static files.

There is no browser here, so these tests check the things that break most
often: missing files, wrong element ids and unsafe JavaScript.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.config import STATIC_DIR

JS_FILES = sorted((STATIC_DIR / "js").glob("*.js"))


def read_html() -> str:
    return (STATIC_DIR / "dashboard.html").read_text(encoding="utf-8")


def test_dashboard_page_is_public_html(client: TestClient) -> None:
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>URL Shortener Dashboard</title>" in response.text


def test_dashboard_with_trailing_slash_redirects(client: TestClient) -> None:
    response = client.get("/dashboard/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith("/dashboard")


def test_every_local_file_used_by_the_page_exists(client: TestClient) -> None:
    paths = re.findall(r'(?:src|href)="(/static/[^"]+)"', read_html())

    assert "/static/js/main.js" in paths
    assert "/static/css/dashboard.css" in paths
    for path in paths:
        assert client.get(path).status_code == 200, path


def test_javascript_files_have_a_javascript_content_type(client: TestClient) -> None:
    assert JS_FILES, "no JavaScript files found"
    for file in JS_FILES:
        response = client.get(f"/static/js/{file.name}")
        assert "javascript" in response.headers["content-type"], file.name


def test_every_javascript_import_points_to_an_existing_file() -> None:
    for file in JS_FILES:
        imports = re.findall(r'from "\./([\w-]+\.js)"', file.read_text("utf-8"))
        for name in imports:
            assert (STATIC_DIR / "js" / name).is_file(), f"{file.name} -> {name}"


def test_javascript_only_uses_element_ids_that_exist_in_the_page() -> None:
    page_ids = set(re.findall(r'\bid="([\w-]+)"', read_html()))
    for file in JS_FILES:
        used = set(re.findall(r'\$\("([\w-]+)"\)', file.read_text("utf-8")))
        assert used <= page_ids, f"{file.name}: {sorted(used - page_ids)}"


def test_chart_js_is_pinned_and_checked_with_an_integrity_hash() -> None:
    html = read_html()
    tag = re.search(r"<script[^>]+chart\.js[^>]*>", html)

    assert tag is not None
    assert re.search(r"chart\.js@\d+\.\d+\.\d+/", tag.group(0)), "version not pinned"
    assert re.search(r'integrity="sha384-[A-Za-z0-9+/=]+"', tag.group(0))
    assert 'crossorigin="anonymous"' in tag.group(0)


@pytest.mark.parametrize(
    "forbidden",
    ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("],
)
def test_javascript_never_builds_html_from_strings(forbidden: str) -> None:
    for file in JS_FILES:
        assert forbidden not in file.read_text("utf-8"), f"{file.name}: {forbidden}"


def test_unknown_static_file_is_404(client: TestClient) -> None:
    assert client.get("/static/js/nope.js").status_code == 404


def test_static_and_dashboard_are_reserved_codes(auth_client: TestClient) -> None:
    for code in ("static", "dashboard"):
        response = auth_client.post(
            "/links", json={"url": "https://example.com", "custom_code": code}
        )
        assert response.status_code == 422
