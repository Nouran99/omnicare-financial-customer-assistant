"""Small structured draft contract returned by the support Crew."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.config import get_settings
from .api import ChatResponse, ToolCallSummary
from .safety import SafetyCheckResult


class AssistantDraft(BaseModel):
    """Bounded Crew output that maps directly to the public response contract."""

    model_config = ConfigDict(extra="forbid")

    response: str
    sources: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    safety_result: SafetyCheckResult
    follow_up_question: str | None = None
    error_code: str | None = None

    @field_validator("response")
    @classmethod
    def validate_response(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("response must not be blank")
        if len(normalized) > get_settings().message_max_length:
            raise ValueError("response exceeds the configured message length")
        return normalized

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: list[str]) -> list[str]:
        settings = get_settings()
        if len(value) > settings.max_sources:
            raise ValueError("sources exceeds the configured limit")
        normalized: list[str] = []
        for source in value:
            cleaned = source.strip()
            if not cleaned or len(cleaned) > settings.source_max_length:
                raise ValueError("sources contain an invalid value")
            if cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    @field_validator("tool_calls")
    @classmethod
    def validate_tool_calls(cls, value: list[ToolCallSummary]) -> list[ToolCallSummary]:
        if len(value) > get_settings().max_tool_calls:
            raise ValueError("tool_calls exceeds the configured limit")
        return value

    @field_validator("follow_up_question")
    @classmethod
    def validate_follow_up_question(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > get_settings().message_max_length:
            raise ValueError("follow_up_question exceeds the configured message length")
        return normalized

    @field_validator("error_code")
    @classmethod
    def validate_error_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > get_settings().tool_status_max_length:
            raise ValueError("error_code exceeds the configured status length")
        return normalized

    def to_chat_response(self) -> ChatResponse:
        """Map validated draft data to the stable public response model."""

        return ChatResponse(
            response=self.response,
            sources=self.sources,
            tool_calls=self.tool_calls,
        )
