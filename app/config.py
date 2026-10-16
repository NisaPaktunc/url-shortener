"""Application settings, loaded from environment variables or a .env file.

Copy .env.example to .env and fill it in. Real environment variables
win over the .env file.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Folder with the dashboard's HTML, CSS and JavaScript files.
STATIC_DIR = Path(__file__).resolve().parent / "static"


def normalize_database_url(url: str) -> str:
    """Make a Postgres URL use the psycopg 3 driver that this project installs.

    Hosting services (Render, Heroku, ...) give a URL that starts with
    `postgres://` or `postgresql://`. SQLAlchemy would read both as the old
    psycopg2 driver, which is not installed. Other URLs (SQLite, or a URL that
    already names a driver) stay as they are.
    """
    for old in ("postgres://", "postgresql://"):
        if url.startswith(old):
            return "postgresql+psycopg://" + url[len(old) :]
    return url


class Settings(BaseSettings):
    """Settings for the app.

    Change DATABASE_URL to move from SQLite to Postgres later,
    for example: postgresql+psycopg://user:pass@localhost/shortener
    """

    app_name: str = "URL Shortener"
    database_url: str = "sqlite:///./shortener.db"

    # Required. The app refuses to start without a long secret key.
    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=30, gt=0)

    # Log level for the app's own logs (one JSON line per request).
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Rate limits, in the form "5/minute". Counted per client IP address.
    # How many reverse proxies stand in front of the app (0 = none).
    # Rate limits use it to find the real client address (see rate_limit.py).
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)

    rate_limit_enabled: bool = True
    login_rate_limit: str = "5/minute"
    create_link_rate_limit: str = "30/minute"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Accept the URL form that hosting services give."""
        return normalize_database_url(value)


settings = Settings()
