"""Saving click records.

record_click is meant to run as a background task, after the redirect
response has already been sent. It opens its own database session
because the request's session may be closed by then.
"""

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.click import Click
from app.services.device_service import detect_device_type

logger = logging.getLogger(__name__)

MAX_REFERRER_LENGTH = 2048


def clean_referrer(referrer: str | None) -> str | None:
    """Return None for a missing or empty referrer, and cut very long ones."""
    if referrer is None or not referrer.strip():
        return None
    return referrer.strip()[:MAX_REFERRER_LENGTH]


def record_click(
    session_factory: Callable[[], Session],
    link_id: int,
    user_agent: str | None,
    referrer: str | None,
) -> None:
    """Save one click. Never raises: a failed click must not break anything.

    Parsing the User-Agent is done here, not in the request, so the
    redirect stays fast.
    """
    try:
        click = Click(
            link_id=link_id,
            device_type=detect_device_type(user_agent).value,
            referrer=clean_referrer(referrer),
        )
        with session_factory() as db:
            db.add(click)
            db.commit()
    except Exception:
        logger.exception("Could not save click for link %s", link_id)
