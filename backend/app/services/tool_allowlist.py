"""Centralized runtime allowlist for model-requested business tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core.config import Settings, get_settings


class ToolAllowlistError(ValueError):
    """Raised before an unapproved model-requested tool can execute."""


class ToolAllowlist:
    """Validate tool names against a settings-defined, startup-time allowlist."""

    def __init__(self, settings: Settings | None = None) -> None:
        resolved_settings = settings or get_settings()
        self._allowed_names = frozenset(
            name.strip()
            for name in resolved_settings.approved_tool_names.split(",")
            if name.strip()
        )

    @property
    def allowed_names(self) -> frozenset[str]:
        """Return the immutable allowlist for diagnostics and tests."""

        return self._allowed_names

    def ensure_allowed(self, tool_name: str) -> None:
        """Reject an unknown tool name before any executor or event recorder runs."""

        if tool_name not in self._allowed_names:
            raise ToolAllowlistError

    def execute(self, tool_name: str, executor: Callable[[], Any]) -> Any:
        """Run a fixed executor only after the model-supplied name is allowed."""

        self.ensure_allowed(tool_name)
        return executor()
