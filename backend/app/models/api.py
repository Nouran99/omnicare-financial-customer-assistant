"""Public API models with strict validation and safe serialization boundaries."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.config import get_settings


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

    user_id: str
    message: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        return _require_trimmed_text(
            value,
            field_name="user_id",
            max_length=get_settings().user_id_max_length,
        )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _require_trimmed_text(
            value,
            field_name="message",
            max_length=get_settings().message_max_length,
        )


class ToolCallSummary(BaseModel):
    """Safe public summary of a tool operation.

    Arguments and result summaries are deliberately bounded strings rather than raw
    dictionaries or provider payloads, which prevents accidental exposure of prompts,
    filesystem paths, claims collections, or credentials through the public response.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    arguments: str | None = None
    result_summary: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _require_trimmed_text(
            value,
            field_name="name",
            max_length=get_settings().tool_name_max_length,
        )

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _require_trimmed_text(
            value,
            field_name="status",
            max_length=get_settings().tool_status_max_length,
        )

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return _require_trimmed_text(
            normalized,
            field_name="arguments",
            max_length=get_settings().tool_arguments_max_length,
        )

    @field_validator("result_summary")
    @classmethod
    def validate_result_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return _require_trimmed_text(
            normalized,
            field_name="result_summary",
            max_length=get_settings().tool_result_max_length,
        )


class ChatResponse(BaseModel):
    """Stable public response contract for every successful chat request."""

    model_config = ConfigDict(extra="forbid")

    response: str
    sources: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)

    @field_validator("response")
    @classmethod
    def validate_response(cls, value: str) -> str:
        return _require_trimmed_text(
            value,
            field_name="response",
            max_length=get_settings().message_max_length,
        )

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: list[str]) -> list[str]:
        settings = get_settings()
        if len(value) > settings.max_sources:
            raise ValueError(f"sources must contain at most {settings.max_sources} items")
        normalized: list[str] = []
        for source in value:
            cleaned = _require_trimmed_text(
                source,
                field_name="source",
                max_length=settings.source_max_length,
            )
            if cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    @field_validator("tool_calls")
    @classmethod
    def validate_tool_calls(cls, value: list[ToolCallSummary]) -> list[ToolCallSummary]:
        max_tool_calls = get_settings().max_tool_calls
        if len(value) > max_tool_calls:
            raise ValueError(
                f"tool_calls must contain at most {max_tool_calls} items"
            )
        return value


class ErrorResponse(BaseModel):
    """Safe error envelope shared by handled API failures."""

    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str
    request_id: str | None = None
