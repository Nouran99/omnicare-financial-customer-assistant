"""Whitelist-based conversion of internal tool events to public API summaries."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ..core.config import Settings, get_settings
from ..models.api import ToolCallSummary
from .tool_allowlist import ToolAllowlist, ToolAllowlistError


class ToolSummarySanitizationError(ValueError):
    """Controlled failure raised when an event cannot be safely summarized."""


def _normalized_patterns(configured: str) -> list[str]:
    return [
        " ".join(pattern.casefold().split())
        for pattern in configured.split(",")
        if " ".join(pattern.casefold().split())
    ]


def _normalized(value: object) -> str:
    return " ".join(str(value).casefold().split())


def _contains_sensitive(value: str, settings: Settings) -> bool:
    normalized = _normalized(value)
    if any(pattern in normalized for pattern in _normalized_patterns(settings.tool_summary_redaction_patterns)):
        return True
    return bool(
        re.search(r"(?:^|\s)/(?:[^\s]+)|(?:^|\s)[A-Za-z]:\\[^\s]+", value)
    )


def _safe_text(value: object, *, max_length: int, settings: Settings) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text or _contains_sensitive(text, settings):
        return None
    return text[:max_length]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _claim_id(value: object, *, settings: Settings) -> str | None:
    candidate = _safe_text(value, max_length=settings.claim_id_max_length, settings=settings)
    if candidate is None:
        return None
    expected = rf"^{re.escape(settings.claim_id_prefix)}[0-9A-F]{{{settings.claim_id_random_hex_length}}}$"
    return candidate if re.fullmatch(expected, candidate.upper()) else None


def _failure_summary(settings: Settings) -> str:
    return settings.tool_summary_failure_response


def sanitize_tool_event(
    event: Mapping[str, Any],
    *,
    settings: Settings | None = None,
) -> ToolCallSummary:
    """Convert one internal event using tool-specific public whitelists."""

    resolved_settings = settings or get_settings()
    name = _safe_text(
        event.get("name"),
        max_length=resolved_settings.tool_name_max_length,
        settings=resolved_settings,
    )
    status = _safe_text(
        event.get("status"),
        max_length=resolved_settings.tool_status_max_length,
        settings=resolved_settings,
    )
    if status is None:
        raise ToolSummarySanitizationError
    try:
        ToolAllowlist(resolved_settings).ensure_allowed(name or "")
    except ToolAllowlistError as exc:
        raise ToolSummarySanitizationError from exc

    arguments = _mapping(event.get("arguments"))
    if name == "search_policy":
        safe_query = _safe_text(
            arguments.get("query", event.get("query")),
            max_length=resolved_settings.tool_arguments_max_length,
            settings=resolved_settings,
        )
        return ToolCallSummary(
            name=name,
            status=status,
            arguments=safe_query,
            result_summary=(
                _safe_text(
                    event.get("result_summary"),
                    max_length=resolved_settings.tool_result_max_length,
                    settings=resolved_settings,
                )
                or _failure_summary(resolved_settings)
            ),
        )

    if name == "get_claim_status":
        safe_claim_id = _safe_text(
            arguments.get("claim_id", event.get("claim_id")),
            max_length=resolved_settings.claim_id_max_length,
            settings=resolved_settings,
        )
        safe_claim_status = _safe_text(
            event.get("claim_status"),
            max_length=resolved_settings.claim_status_max_length,
            settings=resolved_settings,
        )
        if status == "success" and safe_claim_id and safe_claim_status:
            summary = f"Claim status: {safe_claim_status}."
        elif status == "not_found" and safe_claim_id:
            summary = "No claim matched the requested ID."
        else:
            summary = _failure_summary(resolved_settings)
        return ToolCallSummary(
            name=name,
            status=status,
            arguments=safe_claim_id,
            result_summary=summary,
        )

    if name != "submit_claim":
        raise ToolSummarySanitizationError

    confirmation_id = _claim_id(
        event.get("confirmation_id", event.get("claim_id")),
        settings=resolved_settings,
    )
    if status == "success" and confirmation_id:
        summary = f"Claim submitted successfully. Confirmation ID: {confirmation_id}."
    else:
        summary = _failure_summary(resolved_settings)
    return ToolCallSummary(
        name=name,
        status=status,
        arguments=None,
        result_summary=summary,
    )
