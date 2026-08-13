"""Offline unit tests for the US-021 DeepSeek provider adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import ProviderError
from app.providers.deepseek import (
    DeepSeekProvider,
    LLMProvider,
    ProviderMessage,
)


@dataclass
class FakeCompletions:
    response: Any
    failure: Exception | None = None
    requests: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **request: Any) -> Any:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return self.response


@dataclass
class FakeClient:
    completions: FakeCompletions

    @property
    def chat(self) -> SimpleNamespace:
        return SimpleNamespace(completions=self.completions)


def configured_settings() -> Settings:
    return Settings(
        deepseek_api_key="test-key-not-for-network-use",
        deepseek_base_url="https://example.invalid/v1",
        deepseek_model="verified-test-model",
        deepseek_timeout_seconds=30,
    )


def test_adapter_is_lazy_and_uses_configured_openai_compatible_client() -> None:
    fake_completions = FakeCompletions(
        response=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Provider response", tool_calls=[]))]
        )
    )
    factory_calls: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeClient:
        factory_calls.append(kwargs)
        return FakeClient(fake_completions)

    provider = DeepSeekProvider(configured_settings(), client_factory=factory)
    assert factory_calls == []

    result = provider.complete([ProviderMessage(role="user", content="Hello")])

    assert result.content == "Provider response"
    assert result.tool_calls == []
    assert factory_calls == [
        {
            "api_key": "test-key-not-for-network-use",
            "base_url": "https://example.invalid/v1",
            "timeout": 30.0,
        }
    ]
    assert fake_completions.requests == [
        {
            "model": "verified-test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        }
    ]


def test_adapter_normalizes_tool_calls_and_parses_requested_schema() -> None:
    class StructuredAnswer(BaseModel):
        answer: str

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"answer":"Structured result"}',
                    tool_calls=[
                        SimpleNamespace(
                            id="call-1",
                            function=SimpleNamespace(
                                name="search_policy", arguments='{"query":"water"}'
                            ),
                        )
                    ],
                )
            )
        ]
    )
    provider = DeepSeekProvider(
        configured_settings(),
        client_factory=lambda **_: FakeClient(FakeCompletions(response=response)),
    )

    result = provider.complete(
        [ProviderMessage(role="user", content="Find coverage")],
        tools=[{"type": "function", "function": {"name": "search_policy"}}],
        response_schema=StructuredAnswer,
    )

    assert result.parsed == StructuredAnswer(answer="Structured result")
    assert result.tool_calls[0].name == "search_policy"
    assert result.tool_calls[0].arguments == '{"query":"water"}'


def test_provider_failures_are_converted_to_safe_application_errors() -> None:
    raw_error = RuntimeError("provider raw payload and private details")
    provider = DeepSeekProvider(
        configured_settings(),
        client_factory=lambda **_: FakeClient(
            FakeCompletions(response=None, failure=raw_error)
        ),
    )

    with pytest.raises(ProviderError) as error:
        provider.complete([ProviderMessage(role="user", content="Hello")])

    assert "provider raw payload" not in str(error.value)


def test_missing_configuration_does_not_construct_a_client() -> None:
    calls: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeClient:
        calls.append(kwargs)
        raise AssertionError("factory must not be called without configuration")

    provider = DeepSeekProvider(
        Settings(deepseek_api_key=None, deepseek_model=None),
        client_factory=factory,
    )

    with pytest.raises(ProviderError):
        provider.complete([ProviderMessage(role="user", content="Hello")])

    assert calls == []


def test_fake_provider_can_replace_the_adapter_boundary() -> None:
    class FakeProvider:
        def complete(
            self,
            messages: list[ProviderMessage],
            *,
            tools: list[dict[str, Any]] | None = None,
            response_schema: type[BaseModel] | None = None,
        ) -> Any:
            return SimpleNamespace(content="fake", tool_calls=[], parsed=None)

    def invoke(provider: LLMProvider) -> str:
        completion = provider.complete([ProviderMessage(role="user", content="Hello")])
        return completion.content or ""

    assert invoke(FakeProvider()) == "fake"


@pytest.mark.parametrize("timeout", [0, -1])
def test_timeout_setting_must_be_positive(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        Settings(deepseek_timeout_seconds=timeout)


@dataclass
class SequenceCompletions:
    response: Any
    failures_before_success: int = 0
    requests: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **request: Any) -> Any:
        self.requests.append(request)
        if len(self.requests) <= self.failures_before_success:
            raise TimeoutError("transient provider timeout")
        return self.response


def response_with_content(content: str = "Provider response") -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=[])
            )
        ]
    )


def test_provider_retries_three_times_then_returns_eventual_success() -> None:
    completions = SequenceCompletions(
        response=response_with_content(),
        failures_before_success=3,
    )
    settings = configured_settings().model_copy(update={"deepseek_retry_count": 3})
    provider = DeepSeekProvider(
        settings,
        client_factory=lambda **_: FakeClient(completions),
    )

    result = provider.complete([ProviderMessage(role="user", content="Hello")])

    assert result.content == "Provider response"
    assert len(completions.requests) == 4


def test_provider_permanent_failure_is_bounded_by_three_retries() -> None:
    completions = FakeCompletions(
        response=None,
        failure=RuntimeError("permanent provider outage"),
    )
    settings = configured_settings().model_copy(update={"deepseek_retry_count": 3})
    provider = DeepSeekProvider(
        settings,
        client_factory=lambda **_: FakeClient(completions),
    )

    with pytest.raises(ProviderError):
        provider.complete([ProviderMessage(role="user", content="Hello")])

    assert len(completions.requests) == 4


def test_provider_can_disable_retries_for_a_bounded_single_attempt() -> None:
    completions = FakeCompletions(
        response=None,
        failure=RuntimeError("provider outage"),
    )
    settings = configured_settings().model_copy(update={"deepseek_retry_count": 0})
    provider = DeepSeekProvider(
        settings,
        client_factory=lambda **_: FakeClient(completions),
    )

    with pytest.raises(ProviderError):
        provider.complete([ProviderMessage(role="user", content="Hello")])

    assert len(completions.requests) == 1


@pytest.mark.parametrize("retry_count", [-1])
def test_retry_count_must_not_be_negative(retry_count: int) -> None:
    with pytest.raises(ValueError, match="retry_count"):
        Settings(deepseek_retry_count=retry_count)
