"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, settings
from app.errors import register_error_handlers
from app.logging_config import RequestLoggingMiddleware, setup_logging
from app.rate_limit import limiter
from app.routers import auth, dashboard, health, links, redirect, stats

setup_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.state.limiter = limiter  # slowapi looks for it here
register_error_handlers(app)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(links.router)
app.include_router(stats.router)
app.include_router(dashboard.router)
# The dashboard's CSS and JavaScript files.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
# The redirect router must be last: its /{code} route matches any single word.
app.include_router(redirect.router)
