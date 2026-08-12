"""Sanitized JSON logging for request and operational events."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_RESERVED_KEYS = {
    "api_key",
    "authorization",
    "claims",
    "content",
    "message",
    "prompt",
    "secret",
    "token",
    "transcript",
}


class JsonLogFormatter(logging.Formatter):
    """Serialize allowlisted event fields as one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", record.getMessage())
        request_id = getattr(record, "request_id", None)
        fields = getattr(record, "fields", {})
        safe_fields = {
            key: value
            for key, value in fields.items()
            if key.lower() not in _RESERVED_KEYS
        }
        payload: dict[str, Any] = {
            "event": str(event),
            "level": record.levelname,
        }
        if request_id:
            payload["request_id"] = str(request_id)
        payload.update(safe_fields)
        return json.dumps(payload, sort_keys=True, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once with a sanitized stdout handler."""

    normalized_level = level.upper()
    numeric_level = getattr(logging, normalized_level, logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    for handler in root_logger.handlers:
        if getattr(handler, "_omnicare_json_handler", False):
            handler.setLevel(numeric_level)
            return

    handler = logging.StreamHandler(sys.stdout)
    handler._omnicare_json_handler = True  # type: ignore[attr-defined]
    handler.setLevel(numeric_level)
    handler.setFormatter(JsonLogFormatter())
    root_logger.addHandler(handler)


def log_event(
    logger: logging.Logger,
    *,
    event: str,
    request_id: str | None = None,
    **fields: Any,
) -> None:
    """Emit an operational event without accepting sensitive field names."""

    safe_fields = {
        key: value for key, value in fields.items() if key.lower() not in _RESERVED_KEYS
    }
    logger.info(
        event,
        extra={"event": event, "request_id": request_id, "fields": safe_fields},
    )


def log_tool_event(
    logger: logging.Logger,
    *,
    request_id: str | None,
    tool_name: str,
    status: str,
) -> None:
    """Log a tool name and status without arguments or returned records."""

    log_event(
        logger,
        event="tool_invoked",
        request_id=request_id,
        tool_name=tool_name,
        status=status,
    )


def log_provider_failure(
    logger: logging.Logger,
    *,
    request_id: str | None,
    provider: str,
    error_type: str,
) -> None:
    """Log provider failure metadata without prompts or raw provider payloads."""

    log_event(
        logger,
        event="provider_failure",
        request_id=request_id,
        provider=provider,
        error_type=error_type,
    )
