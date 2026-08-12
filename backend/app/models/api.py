"""Public API models with strict validation and safe serialization boundaries."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_USER_ID_LENGTH = 128
MAX_MESSAGE_LENGTH = 8_000
MAX_TOOL_NAME_LENGTH = 64
MAX_TOOL_STATUS_LENGTH = 32
MAX_TOOL_ARGUMENTS_LENGTH = 1_000
MAX_TOOL_RESULT_LENGTH = 2_000


def _require_trimmed_text(value: str, *, field_name: str, max_length: int) -> str:
    """Reject blank text and normalize surrounding whitespace."""

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized


class HealthResponse(BaseModel):
    """Stable process-health response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy"] = "healthy"


class ChatRequest(BaseModel):
    """Validated input contract for the chat endpoint."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1, max_length=MAX_USER_ID_LENGTH)
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        return _require_trimmed_text(
            value, field_name="user_id", max_length=MAX_USER_ID_LENGTH
        )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _require_trimmed_text(
            value, field_name="message", max_length=MAX_MESSAGE_LENGTH
        )


class ToolCallSummary(BaseModel):
    """Safe public summary of a tool operation.

    Arguments and result summaries are deliberately bounded strings rather than raw
    dictionaries or provider payloads, which prevents accidental exposure of prompts,
    filesystem paths, claims collections, or credentials through the public response.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=MAX_TOOL_NAME_LENGTH)
    status: str = Field(..., min_length=1, max_length=MAX_TOOL_STATUS_LENGTH)
    arguments: str | None = Field(default=None, max_length=MAX_TOOL_ARGUMENTS_LENGTH)
    result_summary: str | None = Field(default=None, max_length=MAX_TOOL_RESULT_LENGTH)

    @field_validator("name", "status")
    @classmethod
    def validate_short_text(cls, value: str, info: Any) -> str:
        return _require_trimmed_text(
            value,
            field_name=info.field_name,
            max_length=MAX_TOOL_NAME_LENGTH
            if info.field_name == "name"
            else MAX_TOOL_STATUS_LENGTH,
        )

    @field_validator("arguments", "result_summary")
    @classmethod
    def validate_optional_text(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        max_length = (
            MAX_TOOL_ARGUMENTS_LENGTH
            if info.field_name == "arguments"
            else MAX_TOOL_RESULT_LENGTH
        )
        if len(normalized) > max_length:
            raise ValueError(f"{info.field_name} must be at most {max_length} characters")
        return normalized


class ChatResponse(BaseModel):
    """Stable public response contract for every successful chat request."""

    model_config = ConfigDict(extra="forbid")

    response: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    sources: list[str] = Field(default_factory=list, max_length=20)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list, max_length=20)

    @field_validator("response")
    @classmethod
    def validate_response(cls, value: str) -> str:
        return _require_trimmed_text(
            value, field_name="response", max_length=MAX_MESSAGE_LENGTH
        )

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for source in value:
            cleaned = _require_trimmed_text(
                source, field_name="source", max_length=512
            )
            if cleaned not in normalized:
                normalized.append(cleaned)
        return normalized


class ErrorResponse(BaseModel):
    """Safe error envelope shared by handled API failures."""

    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str
    request_id: str | None = None
