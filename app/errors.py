"""One error format for the whole API, and the handlers that produce it.

Every error answer looks like this:

    {"error": {"code": "not_found", "message": "Short link not found.",
               "request_id": "3f2c..."}}

A 422 answer also has `details`, one entry per wrong field:

    "details": [{"field": "url", "message": "Input should be a valid URL"}]

The input values are never put in the answer (a wrong password field would
otherwise be sent back to the client and could end up in logs).
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


def error_response(
    request: Request,
    status_code: int,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build an error answer in the standard format."""
    request_id = getattr(request.state, "request_id", None)
    error: dict[str, Any] = {
        "code": ERROR_CODES.get(status_code, "http_error"),
        "message": message,
    }
    if request_id:
        error["request_id"] = request_id
        headers = {**(headers or {}), "X-Request-ID": request_id}
    if details is not None:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status_code, headers=headers)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Our own HTTPException errors, and the ones from Starlette (404, 405)."""
    return error_response(
        request,
        exc.status_code,
        str(exc.detail),
        headers=dict(exc.headers) if exc.headers else None,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Wrong request data (422). Lists the fields but not the values."""
    details = [
        {
            # loc is like ("body", "url"): drop the first part ("body"/"query").
            "field": ".".join(str(part) for part in error["loc"][1:]),
            "message": str(error["msg"]),
        }
        for error in exc.errors()
    ]
    return error_response(
        request, 422, "The request data is not valid.", details=details
    )


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Too many requests (429)."""
    retry_after = int(exc.limit.limit.get_expiry())  # the length of the window
    return error_response(
        request,
        429,
        "Too many requests. Please wait a moment and try again.",
        headers={"Retry-After": str(retry_after)},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Anything we did not expect (500). The details go to the log only."""
    logger.error(
        "Unhandled error on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return error_response(request, 500, "Something went wrong on our side.")


def register_error_handlers(app: FastAPI) -> None:
    """Connect all handlers to the app."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
