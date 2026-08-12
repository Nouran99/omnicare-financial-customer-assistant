"""Single-entry OmniCare support Flow for text and voice-transcript requests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from crewai import Crew, Process

from ..core.config import Settings, get_settings
from ..core.errors import ProviderError
from ..models.api import ChatResponse, ToolCallSummary
from ..models.draft import AssistantDraft
from ..models.safety import SafetyCheckResult
from ..providers.deepseek import DeepSeekProvider, LLMProvider
from ..services.draft_validator import (
    DraftValidationError,
    parse_task_output,
    validate_assistant_draft,
)
from ..services.safety_gate import DeterministicSafetyGate
from ..tools.get_claim_status import GetClaimStatusTool
from ..tools.search_policy import SearchPolicyTool
from ..tools.submit_claim import SubmitClaimTool
from .crew import OmniCareSupportCrew
from .state import AssistantState, InputChannel, initialize_assistant_state
from .tasks import support_request_task


class ToolFlowError(RuntimeError):
    """Controlled failure raised when a tool reports a safe failure result."""


class KickoffCrew(Protocol):
    def kickoff(self, *, inputs: Mapping[str, Any]) -> Any:
        ...


class OmniCareSupportFlow:
    """Run every request through one deterministic safety and draft lifecycle."""

    def __init__(
        self,
        *,
        crew: KickoffCrew | None = None,
        provider: LLMProvider | None = None,
        safety_gate: DeterministicSafetyGate | None = None,
        settings: Settings | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider
        self.safety_gate = safety_gate or DeterministicSafetyGate(self.settings)
        self._crew = crew
        self._tools: list[Any] = list(tools or [])

    def run(
        self,
        *,
        user_id: str,
        message: str,
        request_id: str | None = None,
        input_channel: InputChannel = "text",
    ) -> ChatResponse:
        """Process one text or voice-transcript request into a safe ChatResponse."""

        self._reset_tool_observations()
        state = initialize_assistant_state(
            user_id=user_id,
            message=message,
            request_id=request_id,
            input_channel=input_channel,
        )
        state.safety_result = self.safety_gate.check(state.message)
        if not state.safety_result.allowed:
            state.error_code = state.safety_result.reason_code
            state.final_response = self.settings.flow_blocked_response
            return self._response_from_state(state)

        try:
            crew = self._get_crew()
            raw_output = crew.kickoff(
                inputs={
                    "request_id": state.request_id,
                    "user_id": state.user_id,
                    "message": state.message,
                    "input_channel": state.input_channel,
                }
            )
            draft = parse_task_output(raw_output)
            composed_draft = self._compose_with_actual_events(draft)
            validated_draft = validate_assistant_draft(
                composed_draft,
                settings=self.settings,
            )
            self._apply_draft(state, validated_draft)
            return self._response_from_state(state)
        except ToolFlowError:
            state.error_code = "tool_error"
            state.final_response = self.settings.flow_tool_error_response
            return self._response_from_state(state)
        except DraftValidationError:
            state.error_code = "draft_validation_failed"
            state.final_response = self.settings.flow_validation_error_response
            return self._response_from_state(state)
        except ProviderError:
            state.error_code = "provider_error"
            state.final_response = self.settings.flow_provider_error_response
            return self._response_from_state(state)
        except Exception:  # pragma: no cover - final orchestration boundary
            state.error_code = "flow_error"
            state.final_response = self.settings.flow_provider_error_response
            return self._response_from_state(state)

    def _get_crew(self) -> KickoffCrew:
        if self._crew is not None:
            return self._crew

        definition = OmniCareSupportCrew(
            provider=self.provider,
            settings=self.settings,
        )
        agent = definition.support_agent.build()
        task = support_request_task(agent, settings=self.settings)
        self._tools = list(definition.support_agent.tools)
        self._crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
            memory=False,
        )
        return self._crew

    def _compose_with_actual_events(self, draft: AssistantDraft) -> AssistantDraft:
        actual_events: list[ToolCallSummary] = []
        actual_sources: list[str] = []
        had_actual_observation = False
        had_tool_failure = False

        for tool in self._tools:
            if hasattr(tool, "last_output"):
                output = getattr(tool, "last_output", None)
                if output is not None:
                    had_actual_observation = True
                    if output.status == "failure":
                        had_tool_failure = True
                    actual_sources.extend(result.citation for result in output.results)
                    actual_events.append(
                        ToolCallSummary(
                            name=tool.name,
                            status=output.status,
                            result_summary=output.message
                            or "Policy evidence returned.",
                        )
                    )
            elif hasattr(tool, "last_tool_event"):
                event = getattr(tool, "last_tool_event", None)
                if event is not None:
                    had_actual_observation = True
                    if event.status == "failure":
                        had_tool_failure = True
                    actual_events.append(
                        ToolCallSummary(
                            name=event.name,
                            status=event.status,
                            result_summary=event.result_summary,
                        )
                    )

        if had_tool_failure:
            raise ToolFlowError

        if not had_actual_observation:
            return draft

        merged_sources = self._deduplicate(actual_sources + draft.sources)
        return draft.model_copy(
            update={
                "sources": merged_sources,
                "tool_calls": actual_events,
            }
        )

    def _reset_tool_observations(self) -> None:
        for tool in self._tools:
            reset = getattr(tool, "reset_observation", None)
            if callable(reset):
                reset()

    def _apply_draft(self, state: AssistantState, draft: AssistantDraft) -> None:
        state.safety_result = draft.safety_result
        state.draft_response = draft.response
        state.final_response = draft.response
        state.error_code = draft.error_code
        for source in draft.sources:
            state.append_source(source)
        for event in draft.tool_calls:
            state.append_tool_event(event)

    def _response_from_state(self, state: AssistantState) -> ChatResponse:
        response = state.final_response or self.settings.flow_validation_error_response
        return ChatResponse(
            response=response,
            sources=list(state.sources),
            tool_calls=list(state.tool_events),
        )

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value not in result:
                result.append(value)
        return result
