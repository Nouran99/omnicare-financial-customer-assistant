"""Tests for the US-028 bounded OmniCare support Crew definition."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.flows.crew import (
    OmniCareSupportAgent,
    OmniCareSupportCrew,
    ProviderBackedCrewLLM,
)
from app.providers.deepseek import ProviderCompletion, ProviderMessage


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[ProviderMessage], **kwargs: Any) -> ProviderCompletion:
        self.calls += 1
        return ProviderCompletion(content="fake provider response")


def build_settings() -> Settings:
    return Settings(
        deepseek_model="deepseek-v4-flash",
        crew_agent_role="Configured support role",
        crew_agent_goal="Configured support goal",
        crew_agent_backstory="Configured support backstory with citation and safety rules.",
        crew_agent_max_iter=3,
        crew_agent_max_execution_time_seconds=30,
        crew_agent_allow_delegation=False,
        crew_agent_allow_code_execution=False,
        crew_process="sequential",
    )


def test_crew_contains_one_bounded_support_agent_and_only_approved_tools() -> None:
    fake_provider = FakeProvider()
    settings = build_settings()
    crew_definition = OmniCareSupportCrew(provider=fake_provider, settings=settings)

    crew = crew_definition.build()
    agent = crew.agents[0]

    assert len(crew.agents) == 1
    assert crew.process.value == "sequential"
    assert [tool.name for tool in agent.tools] == [
        "search_policy",
        "get_claim_status",
        "submit_claim",
    ]
    assert agent.allow_delegation is False
    assert agent.allow_code_execution is False
    assert agent.max_iter == 3
    assert agent.max_execution_time == 30
    assert agent.role == "Configured support role"
    assert agent.goal == "Configured support goal"
    assert "citation" in agent.backstory.lower()
    assert fake_provider.calls == 0


def test_agent_factory_accepts_fake_provider_without_network_calls() -> None:
    fake_provider = FakeProvider()
    definition = OmniCareSupportAgent(
        provider=fake_provider,
        settings=build_settings(),
    )

    assert [tool.name for tool in definition.build().tools] == [
        "search_policy",
        "get_claim_status",
        "submit_claim",
    ]
    assert fake_provider.calls == 0


def test_claim_tools_receive_injected_settings() -> None:
    settings = Settings(
        deepseek_model="deepseek-v4-flash",
        claims_file_path="/tmp/configured-claims.json",
    )
    definition = OmniCareSupportAgent(provider=FakeProvider(), settings=settings)
    tools = {tool.name: tool for tool in definition.build().tools}

    assert tools["get_claim_status"]._settings is settings
    assert tools["submit_claim"]._settings is settings


def test_provider_bridge_delegates_only_when_explicitly_called() -> None:
    fake_provider = FakeProvider()
    bridge = ProviderBackedCrewLLM(fake_provider, build_settings())

    assert fake_provider.calls == 0
    result = bridge.call("hello")

    assert result == "fake provider response"
    assert fake_provider.calls == 1
