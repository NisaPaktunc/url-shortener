"""Helpers that put test data straight into the database."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Click, Link

# A click to add: (time, device type, referrer)
ClickData = tuple[datetime, str, str | None]


def make_link(
    db: Session,
    owner_id: int | None,
    code: str,
    created_at: datetime | None = None,
) -> Link:
    """Save a link. The owner can be None, like for links from before accounts."""
    link = Link(code=code, target_url=f"https://example.com/{code}", owner_id=owner_id)
    if created_at is not None:
        link.created_at = created_at
    db.add(link)
    db.commit()
    return link


def add_clicks(db: Session, link: Link, clicks: list[ClickData]) -> None:
    """Save many clicks of one link at once."""
    db.add_all(
        Click(link_id=link.id, clicked_at=when, device_type=device, referrer=referrer)
        for when, device, referrer in clicks
    )
    db.commit()
