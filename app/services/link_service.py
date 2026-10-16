"""Business logic for short links.

Routers call these functions. This layer knows nothing about HTTP:
it raises plain Python errors and the routers turn them into responses.
"""

import secrets
import string

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.link import Link

# base62 = 26 lowercase + 26 uppercase + 10 digits
ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_ATTEMPTS = 5


class CodeAlreadyExistsError(Exception):
    """The code is already used by another link."""


class CodeGenerationError(Exception):
    """We could not find a free random code after several tries."""


class LinkNotFoundError(Exception):
    """No link exists for the given code."""


def generate_code() -> str:
    """Make a random 7-character base62 code."""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def create_link(
    db: Session,
    target_url: str,
    owner_id: int,
    custom_code: str | None = None,
) -> Link:
    """Save a new short link owned by a user and return it.

    With a custom code, a taken code raises CodeAlreadyExistsError.
    Without one, we try random codes until one is free.
    """
    if custom_code is not None:
        return _save_link(db, custom_code, target_url, owner_id)

    for _ in range(MAX_ATTEMPTS):
        try:
            return _save_link(db, generate_code(), target_url, owner_id)
        except CodeAlreadyExistsError:
            continue
    raise CodeGenerationError(f"No free code found after {MAX_ATTEMPTS} attempts.")


def get_link_by_code(db: Session, code: str) -> Link:
    """Find a link by its code or raise LinkNotFoundError."""
    link = db.scalar(select(Link).where(Link.code == code))
    if link is None:
        raise LinkNotFoundError(code)
    return link


def _save_link(db: Session, code: str, target_url: str, owner_id: int) -> Link:
    """Insert one row. The unique index on code decides if it is taken.

    Letting the database check this is safe even when two requests
    arrive at the same moment.
    """
    link = Link(code=code, target_url=target_url, owner_id=owner_id)
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise CodeAlreadyExistsError(code) from None
    return link
