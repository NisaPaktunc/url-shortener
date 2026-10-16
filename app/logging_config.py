"""Structured logging: every log line is one JSON object.

JSON lines are easy to search and filter in a log tool. A request log line
looks like this:

    {"time": "2026-10-11T16:20:01+00:00", "level": "INFO",
     "logger": "app.request", "message": "request", "request_id": "ab12...",
     "method": "GET", "path": "/links", "status": 200, "duration_ms": 4.2}

Never log passwords, tokens or query strings.
"""

import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Extra fields that a log call can add with `extra={...}`.
EXTRA_FIELDS = ("request_id", "method", "path", "status", "duration_ms")

request_logger = logging.getLogger("app.request")

# An incoming X-Request-ID is only used if it is short and harmless.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class JsonFormatter(logging.Formatter):
    """Write a log record as one line of JSON."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                data[field] = value
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: str) -> None:
    """Send the app's logs (the "app" logger and below) to stderr as JSON."""
    logger = logging.getLogger("app")
    logger.setLevel(level)
    for handler in list(logger.handlers):
        if getattr(handler, "_json_handler", False):
            logger.removeHandler(handler)  # do not add it twice
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._json_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)


class RequestLoggingMiddleware:
    """Log one line per request: method, path, status and duration.

    It also gives every request an id (header `X-Request-ID`), so a line in
    the log can be matched with an error answer a user got.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        status = 500  # stays 500 if the app crashes before it answers
        start = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                if "x-request-id" not in headers:
                    headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope["path"]  # the query string is not part of it
            # The health check runs every few seconds, so it is only a debug line.
            level = logging.DEBUG if path == "/health" else logging.INFO
            request_logger.log(
                level,
                "request",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
