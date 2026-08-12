"""Typed request state shared by the future OmniCare support Flow."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.config import get_settings
from ..models.api import ChatRequest, ToolCallSummary
from ..models.safety import SafetyCheckResult
from ..tools.schemas import PolicyEvidenceOutput

InputChannel = Literal["text", "voice"]


def _optional_text(value: str | None, *, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} exceeds the configured length")
    return normalized


class AssistantState(BaseModel):
    """Strict, serializable state for one text or voice-assisted request."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    user_id: str
    message: str
    input_channel: InputChannel = "text"
    safety_result: SafetyCheckResult | None = None
    intent: str | None = None
    retrieved_context: list[PolicyEvidenceOutput] = Field(default_factory=list)
    tool_events: list[ToolCallSummary] = Field(default_factory=list)
    draft_response: str | None = None
    final_response: str | None = None
    sources: list[str] = Field(default_factory=list)
    error_code: str | None = None

    @classmethod
    def from_chat_request(
        cls,
        request: ChatRequest,
        *,
        request_id: str | None = None,
        input_channel: InputChannel = "text",
    ) -> "AssistantState":
        return initialize_assistant_state(
            user_id=request.user_id,
            message=request.message,
            request_id=request_id,
            input_channel=input_channel,
        )

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("request_id must not be blank")
        if len(normalized) > get_settings().request_id_max_length:
            raise ValueError("request_id exceeds the configured length")
        return normalized

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("user_id must not be blank")
        if len(normalized) > get_settings().user_id_max_length:
            raise ValueError("user_id exceeds the configured length")
        return normalized

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        if len(normalized) > get_settings().message_max_length:
            raise ValueError("message exceeds the configured length")
        return normalized

    @field_validator("intent", "draft_response", "final_response", "error_code")
    @classmethod
    def validate_optional_text(cls, value: str | None, info: object) -> str | None:
        field_name = getattr(info, "field_name", "state_field")
        settings = get_settings()
        max_length = (
            settings.message_max_length
            if field_name in {"intent", "draft_response", "final_response"}
            else settings.tool_status_max_length
        )
        return _optional_text(value, field_name=field_name, max_length=max_length)

    @field_validator("retrieved_context")
    @classmethod
    def validate_retrieved_context(
        cls, value: list[PolicyEvidenceOutput]
    ) -> list[PolicyEvidenceOutput]:
        if len(value) > get_settings().max_sources:
            raise ValueError("retrieved_context exceeds the configured source limit")
        return value

    @field_validator("tool_events")
    @classmethod
    def validate_tool_events(cls, value: list[ToolCallSummary]) -> list[ToolCallSummary]:
        if len(value) > get_settings().max_tool_calls:
            raise ValueError("tool_events exceeds the configured tool-call limit")
        return value

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: list[str]) -> list[str]:
        settings = get_settings()
        if len(value) > settings.max_sources:
            raise ValueError("sources exceeds the configured source limit")
        normalized: list[str] = []
        for source in value:
            cleaned = source.strip()
            if not cleaned or len(cleaned) > settings.source_max_length:
                raise ValueError("sources contain an invalid value")
            if cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    def append_tool_event(self, event: ToolCallSummary) -> "AssistantState":
        """Append one bounded event without replacing prior events."""

        if len(self.tool_events) >= get_settings().max_tool_calls:
            raise ValueError("tool_events reached the configured limit")
        self.tool_events.append(event)
        return self

    def append_source(self, source: str) -> "AssistantState":
        """Append one deduplicated source without exposing raw retrieval internals."""

        cleaned = source.strip()
        if not cleaned or len(cleaned) > get_settings().source_max_length:
            raise ValueError("source is invalid")
        if cleaned not in self.sources:
            if len(self.sources) >= get_settings().max_sources:
                raise ValueError("sources reached the configured limit")
            self.sources.append(cleaned)
        return self


def initialize_assistant_state(
    *,
    user_id: str,
    message: str,
    request_id: str | None = None,
    input_channel: InputChannel = "text",
) -> AssistantState:
    """Create initial state for text or voice-transcript input."""

    return AssistantState(
        request_id=request_id or str(uuid4()),
        user_id=user_id,
        message=message,
        input_channel=input_channel,
    )
