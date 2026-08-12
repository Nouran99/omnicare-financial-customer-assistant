"""HTTP middleware for request correlation and safe lifecycle logging."""

from __future__ import annotations

import logging
import time
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logging import log_event

logger = logging.getLogger("omnicare.api")
REQUEST_ID_HEADER = "X-Request-ID"


def _valid_request_id(value: str | None) -> str | None:
    """Accept only bounded UUID request IDs supplied by a client."""

    if not value or len(value) > 64:
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID and log metadata without recording request content."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _valid_request_id(request.headers.get(REQUEST_ID_HEADER)) or str(
            uuid4()
        )
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
