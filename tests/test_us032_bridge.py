"""Offline provider-bridge checks for the US-032 policy path."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.flows.crew import ProviderBackedCrewLLM
from app.providers.deepseek import ProviderCompletion, ProviderMessage, ProviderToolCall


class ToolCallingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[ProviderMessage], **kwargs: Any) -> ProviderCompletion:
        del messages, kwargs
        self.calls += 1
        return ProviderCompletion(
            tool_calls=[
                ProviderToolCall(
                    id="call-policy-1",
                    name="search_policy",
                    arguments='{"query":"sudden pipe burst coverage"}',
                )
            ]
        )


def test_provider_bridge_exposes_native_tool_calls_to_crewai() -> None:
    provider = ToolCallingProvider()
    bridge = ProviderBackedCrewLLM(
        provider,
        Settings(deepseek_model="deepseek-v4-flash"),
    )

    result = bridge.call(
        "Find the supplied policy evidence.",
        tools=[{"type": "function", "function": {"name": "search_policy"}}],
    )

    assert bridge.supports_function_calling() is True
    assert result == [
        {
            "id": "call-policy-1",
            "type": "function",
            "function": {
                "name": "search_policy",
                "arguments": '{"query":"sudden pipe burst coverage"}',
            },
        }
    ]
    assert provider.calls == 1


def test_configured_policy_task_instructions_require_retrieval_before_drafting() -> None:
    settings = Settings(deepseek_model="deepseek-v4-flash")

    assert "call search_policy before drafting" in settings.crew_task_description
    assert "cite policy evidence" in settings.crew_task_expected_output.casefold()
