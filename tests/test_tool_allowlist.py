"""Tests for the US-036 runtime tool allowlist."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.flows.crew import ProviderBackedCrewLLM
from app.providers.deepseek import ProviderCompletion, ProviderMessage, ProviderToolCall
from app.services.tool_allowlist import ToolAllowlist, ToolAllowlistError


class FixedProvider:
    def __init__(self, completion: ProviderCompletion) -> None:
        self.completion = completion

    def complete(self, messages: list[ProviderMessage], **kwargs: Any) -> ProviderCompletion:
        del messages, kwargs
        return self.completion


def build_settings() -> Settings:
    return Settings(
        deepseek_model="deepseek-v4-flash",
        approved_tool_names="search_policy,get_claim_status,submit_claim",
    )


def test_all_three_approved_tools_execute_through_the_fixed_registry() -> None:
    allowlist = ToolAllowlist(build_settings())
    executed: list[str] = []

    for name in ("search_policy", "get_claim_status", "submit_claim"):
        result = allowlist.execute(name, lambda name=name: executed.append(name) or name)
        assert result == name

    assert executed == ["search_policy", "get_claim_status", "submit_claim"]


def test_unknown_tool_is_rejected_before_executor_and_file_access() -> None:
    allowlist = ToolAllowlist(build_settings())
    executed = False

    def forbidden_executor() -> None:
        nonlocal executed
        executed = True

    with pytest.raises(ToolAllowlistError):
        allowlist.execute("run_shell", forbidden_executor)

    assert executed is False


def test_provider_bridge_rejects_model_requested_unknown_tool_before_crewai_execution() -> None:
    provider = FixedProvider(
        ProviderCompletion(
            tool_calls=[
                ProviderToolCall(
                    id="unknown-tool-call",
                    name="arbitrary_filesystem_tool",
                    arguments='{"path":"/tmp/claims.json"}',
                )
            ]
        )
    )
    bridge = ProviderBackedCrewLLM(provider, build_settings())

    with pytest.raises(ToolAllowlistError):
        bridge.call("A model requested an unknown tool.")
