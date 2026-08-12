"""Safe exception mapping for API, provider, tool, and unexpected failures."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from ..models.api import ErrorResponse
from .logging import log_event

logger = logging.getLogger("omnicare.errors")


class ApplicationError(Exception):
    """Base class for errors with a safe public mapping."""

    error_code = "application_error"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    public_detail = "The request could not be completed."


class ProviderError(ApplicationError):
    """An upstream model/provider operation failed."""

    error_code = "provider_error"
    http_status = status.HTTP_502_BAD_GATEWAY
    public_detail = "The assistant provider is temporarily unavailable."


class ToolError(ApplicationError):
    """A bounded operational tool failed safely."""

    error_code = "tool_error"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    public_detail = "The requested operation could not be completed."


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _response(
    request: Request,
    *,
    error: str,
    detail: str,
    http_status: int,
) -> JSONResponse:
    body = ErrorResponse(
        error=error,
        detail=detail,
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=http_status, content=body.model_dump())


async def application_error_handler(
    request: Request, exc: ApplicationError
) -> JSONResponse:
    log_event(
        logger,
        event="application_error",
        request_id=_request_id(request),
        error_code=exc.error_code,
        status_code=exc.http_status,
    )
    return _response(
        request,
        error=exc.error_code,
        detail=exc.public_detail,
        http_status=exc.http_status,
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    log_event(
        logger,
        event="validation_error",
        request_id=_request_id(request),
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
    return _response(
        request,
        error="validation_error",
        detail="Request validation failed.",
        http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    safe_detail = (
        exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    )
    return _response(
        request,
        error="http_error",
        detail=safe_detail,
        http_status=exc.status_code,
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log_event(
        logger,
        event="unexpected_error",
        request_id=_request_id(request),
        exception_type=type(exc).__name__,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    return _response(
        request,
        error="internal_error",
        detail="An unexpected server error occurred.",
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the public error contract without exposing internal diagnostics."""

    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
