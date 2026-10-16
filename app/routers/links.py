"""Endpoints for creating short links and listing them."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.rate_limit import create_link_limit, limiter
from app.schemas.link import LinkCreate, LinkRead
from app.schemas.stats import LinkSummary
from app.services import link_service, stats_service

router = APIRouter(tags=["links"])


@router.get("/links", response_model=list[LinkSummary])
def list_links(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[LinkSummary]:
    """List the logged-in user's links, newest first, with their click totals."""
    rows = stats_service.list_links_with_counts(db, current_user.id)
    return [
        LinkSummary(
            code=link.code,
            short_url=str(request.url_for("redirect_to_target", code=link.code)),
            target_url=link.target_url,
            created_at=link.created_at,
            total_clicks=total_clicks,
        )
        for link, total_clicks in rows
    ]


@router.post("/links", response_model=LinkRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(create_link_limit)
def create_link(
    payload: LinkCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LinkRead:
    """Create a short link, with a random code or a custom one. Login needed.

    Limited per client IP address (30 per minute by default).
    """
    try:
        link = link_service.create_link(
            db,
            str(payload.url),
            owner_id=current_user.id,
            custom_code=payload.custom_code,
        )
    except link_service.CodeAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This custom code is already in use.",
        ) from None
    except link_service.CodeGenerationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create a unique code. Please try again.",
        ) from None

    return LinkRead(
        code=link.code,
        short_url=str(request.url_for("redirect_to_target", code=link.code)),
        target_url=link.target_url,
        created_at=link.created_at,
    )
