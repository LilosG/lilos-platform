"""HTTP middleware for request context and correlation."""

import logging
import re
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.app.context import bind_correlation_id, reset_correlation_id

CORRELATION_ID_HEADER = "X-Correlation-ID"
MAX_CORRELATION_ID_LENGTH = 64
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$", re.ASCII)

logger = logging.getLogger("lilos.api.requests")


def is_valid_correlation_id(value: str | None) -> bool:
    """Return whether a client correlation ID satisfies the public contract."""
    return value is not None and CORRELATION_ID_PATTERN.fullmatch(value) is not None


def resolve_correlation_id(value: str | None) -> str:
    """Accept a valid client value or generate a canonical UUIDv4."""
    if value is not None and is_valid_correlation_id(value):
        return value
    return str(uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind and return a bounded correlation ID for every HTTP request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = resolve_correlation_id(request.headers.get(CORRELATION_ID_HEADER))
        request.state.correlation_id = correlation_id
        token = bind_correlation_id(correlation_id)
        started_at = perf_counter()
        try:
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            logger.info(
                "API request completed",
                extra={
                    "event_name": "api.request.completed",
                    "method": request.method,
                    "route": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                    "outcome": "success" if response.status_code < 400 else "failure",
                },
            )
            return response
        finally:
            reset_correlation_id(token)
