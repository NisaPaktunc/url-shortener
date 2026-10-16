"""The dashboard page.

It is one plain HTML file. It needs no login to load, because all the data
comes from the API, and the API checks the login.
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import STATIC_DIR

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    """Send the dashboard page."""
    return FileResponse(STATIC_DIR / "dashboard.html", media_type="text/html")
