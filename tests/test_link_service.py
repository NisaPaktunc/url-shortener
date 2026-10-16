"""Tests for the link service, without any HTTP involved."""

import re

import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.services import link_service


def test_generate_code_has_7_base62_characters() -> None:
    assert re.fullmatch(r"[A-Za-z0-9]{7}", link_service.generate_code())


def test_generate_code_is_random() -> None:
    codes = {link_service.generate_code() for _ in range(100)}

    assert len(codes) == 100


def test_create_link_saves_and_can_be_found(db_session: Session, user: User) -> None:
    link = link_service.create_link(db_session, "https://example.com", user.id)

    found = link_service.get_link_by_code(db_session, link.code)

    assert found.target_url == "https://example.com"
    assert found.owner_id == user.id


def test_duplicate_custom_code_raises(db_session: Session, user: User) -> None:
    link_service.create_link(db_session, "https://example.com", user.id, "mycode")

    with pytest.raises(link_service.CodeAlreadyExistsError):
        link_service.create_link(db_session, "https://other.com", user.id, "mycode")


def test_unknown_code_raises(db_session: Session) -> None:
    with pytest.raises(link_service.LinkNotFoundError):
        link_service.get_link_by_code(db_session, "nothere")
