"""HTTP middleware for request correlation and safe lifecycle logging."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import get_settings
from .logging import log_event

logger = logging.getLogger("omnicare.api")
REQUEST_ID_HEADER = "X-Request-ID"


def _valid_request_id(value: str | None, *, max_length: int) -> str | None:
    """Accept bounded, printable request IDs supplied by a client."""

    if not value:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        return None
    return normalized


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID and log metadata without recording request content."""

    async def dispatch(self, request: Request, call_next) -> Response:
        runtime_settings = getattr(request.app.state, "settings", None) or get_settings()
        request_id = _valid_request_id(
            request.headers.get(REQUEST_ID_HEADER),
            max_length=runtime_settings.request_id_max_length,
        ) or str(uuid4())
        request.state.request_id = request_id
        started_at = time.perf_counter()
        log_event(
            logger,
            event="request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                event="request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=elapsed_ms,
                status_code=500,
            )
            raise

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        log_event(
            logger,
            event="request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            duration_ms=elapsed_ms,
            status_code=response.status_code,
        )
        return response
