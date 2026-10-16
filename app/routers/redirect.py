"""Endpoint that sends visitors from a short code to the real URL."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, get_session_factory
from app.services import click_service, link_service

router = APIRouter(tags=["redirect"])


@router.get("/{code}", name="redirect_to_target")
def redirect_to_target(
    code: str,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
    user_agent: Annotated[str | None, Header()] = None,
    referer: Annotated[str | None, Header()] = None,
) -> RedirectResponse:
    """Redirect to the target URL (302), or return 404 if the code is unknown.

    The click is saved in a background task, after the response is sent,
    so saving it never slows the redirect down.
    """
    try:
        link = link_service.get_link_by_code(db, code)
    except link_service.LinkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short link not found.",
        ) from None

    # "Referer" is the real (misspelled) name of the HTTP header.
    background_tasks.add_task(
        click_service.record_click, session_factory, link.id, user_agent, referer
    )
    return RedirectResponse(url=link.target_url, status_code=status.HTTP_302_FOUND)
