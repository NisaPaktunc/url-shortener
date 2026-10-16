"""Endpoint for the statistics of one link."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.stats import (
    DailyClicks,
    DeviceBreakdown,
    LinkStatsRead,
    ReferrerCount,
)
from app.services import link_service, stats_service

router = APIRouter(tags=["stats"])


@router.get("/links/{code}/stats", response_model=LinkStatsRead)
def get_link_stats(
    code: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    days: Annotated[
        int, Query(ge=1, le=365, description="Last N days, today included")
    ] = 30,
) -> LinkStatsRead:
    """Click statistics of one of the user's links for the last `days` days.

    A link that belongs to someone else gets the same 404 as a link that
    does not exist.
    """
    try:
        stats = stats_service.get_link_stats(db, current_user.id, code, days)
    except link_service.LinkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short link not found.",
        ) from None

    return LinkStatsRead(
        code=stats.code,
        days=stats.days,
        total_clicks=stats.total_clicks,
        daily=[DailyClicks(date=day, clicks=clicks) for day, clicks in stats.daily],
        devices=DeviceBreakdown(**stats.devices),
        top_referrers=[
            ReferrerCount(referrer=referrer, clicks=clicks)
            for referrer, clicks in stats.top_referrers
        ],
    )
