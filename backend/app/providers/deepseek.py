"""Replaceable DeepSeek adapter over the OpenAI-compatible chat-completions API."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal, Protocol

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.config import Settings, get_settings
from ..core.errors import ProviderError
from ..core.logging import log_provider_failure

logger = logging.getLogger("omnicare.providers.deepseek")


class ProviderMessage(BaseModel):
    """Bounded, OpenAI-compatible message input for the provider boundary."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must not be blank")
        if len(normalized) > get_settings().message_max_length:
            raise ValueError("content exceeds the configured message length")
        return normalized


class ProviderToolCall(BaseModel):
    """Safe normalized representation of a provider tool-call request."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(...)
    name: str = Field(...)
    arguments: str = Field(...)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("tool-call id must not be blank")
        if len(normalized) > get_settings().request_id_max_length:
            raise ValueError("tool-call id exceeds the configured length")
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("tool-call name must not be blank")
        if len(normalized) > get_settings().tool_name_max_length:
            raise ValueError("tool-call name exceeds the configured length")
        return normalized

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, value: str) -> str:
        if len(value) > get_settings().tool_arguments_max_length:
            raise ValueError("tool-call arguments exceed the configured length")
        return value


class ProviderCompletion(BaseModel):
    """Normalized provider output without raw SDK objects or response payloads."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    content: str | None = None
    tool_calls: list[ProviderToolCall] = Field(default_factory=list)
    parsed: BaseModel | None = None


class LLMProvider(Protocol):
    """Replaceable provider boundary for CrewAI and application orchestration."""

    def complete(
        self,
        messages: Sequence[ProviderMessage],
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        response_schema: type[BaseModel] | None = None,
    ) -> ProviderCompletion:
        ...


class DeepSeekProvider:
    """Lazily constructed DeepSeek client using OpenAI-compatible configuration.

    Construction is deliberately side-effect free: no client, network connection, or
    provider call happens until ``complete`` is explicitly invoked. Tests can inject a
    fake client factory and no production credential is read into logs or responses.
    """

    provider_name = "deepseek"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client_factory: Callable[..., Any] = OpenAI,
    ) -> None:
        self._settings = settings or get_settings()
        self._client_factory = client_factory
        self._client: Any | None = None

    def complete(
        self,
        messages: Sequence[ProviderMessage],
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        response_schema: type[BaseModel] | None = None,
    ) -> ProviderCompletion:
        """Create one normalized completion or raise a controlled ``ProviderError``."""

        if not messages:
            raise ProviderError
        try:
            client = self._get_client()
            request: dict[str, Any] = {
                "model": self._required_model(),
                "messages": [message.model_dump() for message in messages],
            }
            if tools:
                request["tools"] = list(tools)
            completion = client.chat.completions.create(**request)
            return self._normalize_completion(completion, response_schema=response_schema)
        except ProviderError:
            raise
        except (OpenAIError, ValueError, TypeError, KeyError, AttributeError) as exc:
            self._log_failure(exc)
            raise ProviderError from exc
        except Exception as exc:  # pragma: no cover - defensive SDK boundary
            self._log_failure(exc)
            raise ProviderError from exc

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = self._settings.deepseek_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise ProviderError
        self._client = self._client_factory(
            api_key=api_key.get_secret_value(),
            base_url=self._settings.deepseek_base_url,
            timeout=self._settings.deepseek_timeout_seconds,
        )
        return self._client

    def _required_model(self) -> str:
        model = self._settings.deepseek_model
        if not model or not model.strip():
            raise ProviderError
        return model.strip()

    def _normalize_completion(
        self,
        completion: Any,
        *,
        response_schema: type[BaseModel] | None,
    ) -> ProviderCompletion:
        choices = getattr(completion, "choices", None)
        if not choices:
            raise ProviderError
        message = getattr(choices[0], "message", None)
        if message is None:
            raise ProviderError

        content = getattr(message, "content", None)
        if content is not None and not isinstance(content, str):
            raise ProviderError
        tool_calls = self._normalize_tool_calls(getattr(message, "tool_calls", None))
        parsed = None
        if response_schema is not None:
            if not content:
                raise ProviderError
            try:
                parsed = response_schema.model_validate_json(content)
            except Exception as exc:
                self._log_failure(exc)
                raise ProviderError from exc
        return ProviderCompletion(content=content, tool_calls=tool_calls, parsed=parsed)

    @staticmethod
    def _normalize_tool_calls(tool_calls: Any) -> list[ProviderToolCall]:
        if not tool_calls:
            return []
        normalized: list[ProviderToolCall] = []
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            normalized.append(
                ProviderToolCall(
                    id=str(getattr(tool_call, "id", "")),
                    name=str(getattr(function, "name", "")),
                    arguments=str(getattr(function, "arguments", "")),
                )
            )
        return normalized

    def _log_failure(self, exc: Exception) -> None:
        log_provider_failure(
            logger,
            request_id=None,
            provider=self.provider_name,
            error_type=type(exc).__name__,
        )
