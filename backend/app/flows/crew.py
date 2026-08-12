"""Bounded CrewAI agent and Crew definitions for US-028."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from crewai import Agent, Crew, Process
from crewai.llms.base_llm import BaseLLM
from pydantic import BaseModel, PrivateAttr

from ..core.config import Settings, get_settings
from ..core.errors import ProviderError
from ..providers.deepseek import (
    DeepSeekProvider,
    LLMProvider,
    ProviderCompletion,
    ProviderMessage,
)
from ..tools.get_claim_status import GetClaimStatusTool
from ..tools.search_policy import SearchPolicyTool
from ..tools.submit_claim import SubmitClaimTool


class ProviderBackedCrewLLM(BaseLLM):
    """Adapt the application provider protocol to CrewAI's BaseLLM boundary."""

    _provider: LLMProvider = PrivateAttr()

    def __init__(self, provider: LLMProvider, settings: Settings) -> None:
        model = settings.deepseek_model or "configured-provider-model"
        super().__init__(
            model=model,
            provider="deepseek",
            temperature=None,
            max_tokens=None,
        )
        self._provider = provider

    def call(
        self,
        messages: str | list[Any],
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Any | None = None,
        from_agent: Any | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> str | Any:
        del callbacks, available_functions, from_task, from_agent
        provider_messages = self._normalize_messages(messages)
        completion = self._provider.complete(
            provider_messages,
            tools=tools,
            response_schema=response_model,
        )
        if completion.parsed is not None:
            return completion.parsed
        if completion.tool_calls:
            return [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    },
                }
                for tool_call in completion.tool_calls
            ]
        if completion.content is None:
            raise ProviderError
        return completion.content

    def supports_function_calling(self) -> bool:
        """Tell CrewAI to use its native tool execution loop."""

        return True

    @staticmethod
    def _normalize_messages(messages: str | list[Any]) -> list[ProviderMessage]:
        if isinstance(messages, str):
            return [ProviderMessage(role="user", content=messages)]
        normalized: list[ProviderMessage] = []
        for message in messages:
            role = getattr(message, "role", None)
            content = getattr(message, "content", None)
            tool_calls = getattr(message, "tool_calls", None)
            if isinstance(message, Mapping):
                role = message.get("role")
                content = message.get("content")
                tool_calls = message.get("tool_calls")
            if role not in {"system", "user", "assistant", "tool"}:
                raise ProviderError
            if content is None and role == "assistant" and tool_calls:
                names = [
                    str(call.get("function", {}).get("name", "tool"))
                    for call in tool_calls
                    if isinstance(call, Mapping)
                ]
                content = "Tool calls requested: " + ", ".join(names or ["tool"])
            elif content is not None and role == "tool":
                role = "user"
                content = f"Trusted tool result: {content}"
            if not isinstance(content, str) or not content.strip():
                raise ProviderError
            normalized.append(ProviderMessage(role=role, content=content))
        if not normalized:
            raise ProviderError
        return normalized


class OmniCareSupportAgent:
    """Factory-style definition for the one bounded support agent."""

    def __init__(
        self,
        *,
        provider: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or DeepSeekProvider(self.settings)
        self.tools = [
            SearchPolicyTool(),
            GetClaimStatusTool(settings=self.settings),
            SubmitClaimTool(settings=self.settings),
        ]
        self.llm = ProviderBackedCrewLLM(self.provider, self.settings)
        self.agent = Agent(
            role=self.settings.crew_agent_role,
            goal=self.settings.crew_agent_goal,
            backstory=self.settings.crew_agent_backstory,
            tools=self.tools,
            llm=self.llm,
            allow_delegation=self.settings.crew_agent_allow_delegation,
            allow_code_execution=self.settings.crew_agent_allow_code_execution,
            max_iter=self.settings.crew_agent_max_iter,
            max_execution_time=self.settings.crew_agent_max_execution_time_seconds,
            verbose=False,
        )

    def build(self) -> Agent:
        """Return the configured CrewAI support agent."""

        return self.agent


class OmniCareSupportCrew:
    """Factory-style definition for the initial single-agent sequential Crew."""

    def __init__(
        self,
        *,
        agent_definition: OmniCareSupportAgent | None = None,
        provider: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.support_agent = agent_definition or OmniCareSupportAgent(
            provider=provider,
            settings=self.settings,
        )
        self.crew = Crew(
            agents=[self.support_agent.build()],
            tasks=[],
            process=Process.sequential,
            verbose=False,
            memory=False,
        )

    def build(self) -> Crew:
        """Return the configured CrewAI Crew."""

        return self.crew
