"""Deterministic pre-LLM safety gate for explicit prompt-injection indicators."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from ..core.config import Settings, get_settings
from ..models.safety import SafetyCheckResult

T = TypeVar("T")


class DeterministicSafetyGate:
    """Prototype keyword gate; this is not a complete prompt-injection detector."""

    _GROUPS = {
        "system_prompt": (
            "safety_system_prompt_patterns",
            "prompt_injection",
            "safety_prompt_injection_reason",
        ),
        "hidden_data": (
            "safety_hidden_data_patterns",
            "hidden_data_access",
            "safety_hidden_data_reason",
        ),
        "tool_bypass": (
            "safety_tool_bypass_patterns",
            "tool_bypass",
            "safety_tool_bypass_reason",
        ),
        "admin_impersonation": (
            "safety_admin_impersonation_patterns",
            "administrator_impersonation",
            "safety_admin_impersonation_reason",
        ),
        "required_field_bypass": (
            "safety_required_field_bypass_patterns",
            "required_field_bypass",
            "safety_required_field_bypass_reason",
        ),
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def check(self, message: str) -> SafetyCheckResult:
        """Normalize and classify one message without invoking any external service."""

        normalized = self._normalize(message)
        if not normalized:
            return SafetyCheckResult.allowed_result(self._settings.safety_allowed_reason)

        for group_name in self._priority():
            pattern_field, reason_code, reason_field = self._GROUPS[group_name]
            patterns = self._patterns(getattr(self._settings, pattern_field))
            if any(pattern in normalized for pattern in patterns):
                return SafetyCheckResult.blocked_result(
                    reason_code=reason_code,  # type: ignore[arg-type]
                    reason=getattr(self._settings, reason_field),
                )
        return SafetyCheckResult.allowed_result(self._settings.safety_allowed_reason)

    def run(
        self,
        message: str,
        action: Callable[[], T],
    ) -> tuple[SafetyCheckResult, T | None]:
        """Run an action only when the normalized message is allowed."""

        result = self.check(message)
        if not result.allowed:
            return result, None
        return result, action()

    def _priority(self) -> list[str]:
        configured = self._settings.safety_pattern_priority.split(",")
        return [
            name.strip()
            for name in configured
            if name.strip() in self._GROUPS
        ]

    @staticmethod
    def _normalize(message: str) -> str:
        return " ".join(message.casefold().split())

    @staticmethod
    def _patterns(configured: str) -> list[str]:
        return [
            " ".join(pattern.casefold().split())
            for pattern in configured.split(",")
            if " ".join(pattern.casefold().split())
        ]
