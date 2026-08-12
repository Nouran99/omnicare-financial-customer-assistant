"""Typed deterministic safety-gate results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..core.config import get_settings

SafetyReasonCode = Literal[
    "allowed",
    "prompt_injection",
    "hidden_data_access",
    "tool_bypass",
    "administrator_impersonation",
    "required_field_bypass",
]


class SafetyCheckResult(BaseModel):
    """Safe result returned before any LLM, tool, or file operation."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reason_code: SafetyReasonCode
    reason: str = Field(...)

    @classmethod
    def allowed_result(cls, reason: str | None = None) -> "SafetyCheckResult":
        return cls(
            allowed=True,
            reason_code="allowed",
            reason=reason if reason is not None else get_settings().safety_allowed_reason,
        )

    @classmethod
    def blocked_result(
        cls,
        reason_code: Literal[
            "prompt_injection",
            "hidden_data_access",
            "tool_bypass",
            "administrator_impersonation",
            "required_field_bypass",
        ],
        reason: str,
    ) -> "SafetyCheckResult":
        return cls(allowed=False, reason_code=reason_code, reason=reason)
