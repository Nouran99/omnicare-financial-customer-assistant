"""Single-entry OmniCare support Flow for text and voice-transcript requests."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Protocol

from crewai import Crew, Process

from ..core.config import Settings, get_settings
from ..core.errors import ProviderError
from ..models.api import ChatResponse, ToolCallSummary
from ..models.claims import ClaimToolEvent
from ..models.draft import AssistantDraft
from ..models.safety import SafetyCheckResult
from ..providers.deepseek import DeepSeekProvider, LLMProvider
from ..services.draft_validator import (
    DraftValidationError,
    parse_task_output,
    validate_assistant_draft,
)
from ..services.tool_allowlist import ToolAllowlist, ToolAllowlistError
from ..services.tool_summary_sanitizer import (
    ToolSummarySanitizationError,
    sanitize_tool_event,
)
from ..services.safety_gate import DeterministicSafetyGate
from ..tools.get_claim_status import GetClaimStatusTool
from ..tools.search_policy import SearchPolicyTool
from ..tools.submit_claim import SubmitClaimTool
from ..tools.schemas import GetClaimStatusOutput, SearchPolicyOutput
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
        self._tool_allowlist = ToolAllowlist(self.settings)
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

        preflight_output: SearchPolicyOutput | None = None
        preflight_query: str | None = None
        preflight_claim_event: ClaimToolEvent | None = None
        try:
            crew = self._get_crew()
            policy_evidence, preflight_output, preflight_query = (
                self._preflight_policy_if_needed(state.message)
            )
            preflight_claim_event = self._preflight_claim_status_if_needed(
                state.message
            )
            raw_output = crew.kickoff(
                inputs={
                    "request_id": state.request_id,
                    "user_id": state.user_id,
                    "message": state.message,
                    "input_channel": state.input_channel,
                    "policy_evidence": policy_evidence,
                }
            )
            draft = parse_task_output(raw_output)
            composed_draft = self._compose_with_actual_events(
                draft,
                preflight_output=preflight_output,
                preflight_query=preflight_query,
                preflight_claim_event=preflight_claim_event,
            )
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
            grounded_response = self._grounded_policy_fallback_response(
                preflight_output=preflight_output,
                preflight_query=preflight_query,
            )
            if grounded_response is not None:
                return grounded_response
            claim_status_response = self._claim_status_fallback_response(
                preflight_claim_event
            )
            if claim_status_response is not None:
                return claim_status_response
            state.error_code = "draft_validation_failed"
            state.final_response = self.settings.flow_validation_error_response
            return self._response_from_state(state)
        except ProviderError:
            grounded_response = self._grounded_policy_fallback_response(
                preflight_output=preflight_output,
                preflight_query=preflight_query,
            )
            if grounded_response is not None:
                return grounded_response
            claim_status_response = self._claim_status_fallback_response(
                preflight_claim_event
            )
            if claim_status_response is not None:
                return claim_status_response
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

    def _preflight_policy_if_needed(
        self,
        message: str,
    ) -> tuple[str, SearchPolicyOutput | None, str | None]:
        """Retrieve trusted policy evidence before the agent drafts coverage answers."""

        if not self._is_policy_coverage_request(message):
            return "", None, None

        policy_tool = next(
            (
                tool
                for tool in self._tools
                if isinstance(tool, SearchPolicyTool)
            ),
            None,
        )
        if policy_tool is None:
            return "", None, None

        try:
            self._tool_allowlist.ensure_allowed(policy_tool.name)
            output = policy_tool._run(message)
        except Exception as exc:  # pragma: no cover - defensive tool boundary
            raise ToolFlowError from exc

        if output.status == "failure":
            raise ToolFlowError
        return policy_tool.evidence_context(), output, message

    def _preflight_claim_status_if_needed(
        self,
        message: str,
    ) -> ClaimToolEvent | None:
        """Run the read-only claim lookup before the agent drafts a status answer."""

        normalized = message.casefold()
        has_intent = any(
            pattern.strip().casefold() in normalized
            for pattern in self.settings.claim_status_intent_patterns.split(",")
            if pattern.strip()
        )
        has_exclusion = any(
            pattern.strip().casefold() in normalized
            for pattern in self.settings.claim_status_exclusion_patterns.split(",")
            if pattern.strip()
        )
        if not has_intent or has_exclusion:
            return None

        claim_id_pattern = re.escape(self.settings.claim_id_prefix)
        claim_id_pattern += rf"[A-Za-z0-9]{{1,{self.settings.claim_id_max_length}}}"
        match = re.search(claim_id_pattern, message, flags=re.IGNORECASE)
        if match is None:
            return None

        status_tool = next(
            (
                tool
                for tool in self._tools
                if isinstance(tool, GetClaimStatusTool)
            ),
            None,
        )
        if status_tool is None:
            return None

        claim_id = match.group(0).upper()
        try:
            self._tool_allowlist.ensure_allowed(status_tool.name)
            output: GetClaimStatusOutput = status_tool._run(claim_id)
        except Exception as exc:  # pragma: no cover - defensive tool boundary
            raise ToolFlowError from exc

        if output.status == "failure":
            raise ToolFlowError
        return status_tool.last_tool_event

    def _grounded_policy_fallback_response(
        self,
        *,
        preflight_output: SearchPolicyOutput | None,
        preflight_query: str | None,
    ) -> ChatResponse | None:
        """Return trusted evidence when generation fails after successful preflight."""

        if preflight_output is None or preflight_output.status != "success":
            return None
        try:
            self._tool_allowlist.ensure_allowed("search_policy")
            sources = self._deduplicate(
                result.citation for result in preflight_output.results
            )
            events = [
                sanitize_tool_event(
                    {
                        "name": "search_policy",
                        "status": "success",
                        "query": preflight_query,
                        "result_summary": "Policy evidence returned.",
                    },
                    settings=self.settings,
                )
            ]
            evidence = "\n".join(
                f"{result.citation}: {result.text}"
                for result in preflight_output.results
            )
            response = self.settings.flow_grounded_policy_fallback_prefix + evidence
            return ChatResponse(
                response=response,
                sources=sources,
                tool_calls=events,
            )
        except (ToolAllowlistError, ToolSummarySanitizationError, ValueError):
            return None

    def _claim_status_fallback_response(
        self,
        event: ClaimToolEvent | None,
    ) -> ChatResponse | None:
        """Return a bounded claim status when generation fails after lookup."""

        if event is None or event.status not in {"success", "not_found"}:
            return None
        if not event.claim_id:
            return None
        try:
            self._tool_allowlist.ensure_allowed(event.name)
            if event.status == "success" and event.claim_status:
                response = (
                    self.settings.flow_claim_status_fallback_prefix
                    + event.claim_id
                    + self.settings.flow_claim_status_fallback_separator
                    + event.claim_status
                    + self.settings.flow_claim_status_fallback_suffix
                )
            else:
                response = (
                    self.settings.flow_claim_not_found_fallback_prefix
                    + event.claim_id
                    + self.settings.flow_claim_not_found_fallback_suffix
                )
            summary = sanitize_tool_event(
                event.model_dump(),
                settings=self.settings,
            )
            return ChatResponse(response=response, sources=[], tool_calls=[summary])
        except (ToolAllowlistError, ToolSummarySanitizationError, ValueError):
            return None

    def _is_policy_coverage_request(self, message: str) -> bool:
        normalized = message.casefold()
        has_intent = any(
            pattern.strip().casefold() in normalized
            for pattern in self.settings.policy_query_intent_patterns.split(",")
            if pattern.strip()
        )
        has_exclusion = any(
            pattern.strip().casefold() in normalized
            for pattern in self.settings.policy_query_exclusion_patterns.split(",")
            if pattern.strip()
        )
        return has_intent and not has_exclusion

    def _compose_with_actual_events(
        self,
        draft: AssistantDraft,
        *,
        preflight_output: SearchPolicyOutput | None = None,
        preflight_query: str | None = None,
        preflight_claim_event: ClaimToolEvent | None = None,
    ) -> AssistantDraft:
        actual_events: list[ToolCallSummary] = []
        actual_sources: list[str] = []
        had_actual_observation = False
        had_tool_failure = False

        for tool in self._tools:
            if hasattr(tool, "last_output"):
                output = getattr(tool, "last_output", None)
                query = getattr(tool, "last_query", None)
                if (
                    isinstance(tool, SearchPolicyTool)
                    and preflight_output is not None
                    and preflight_output.status == "success"
                ):
                    output = preflight_output
                    query = preflight_query
                if output is not None:
                    had_actual_observation = True
                    if output.status == "failure":
                        had_tool_failure = True
                    actual_sources.extend(result.citation for result in output.results)
                    try:
                        self._tool_allowlist.ensure_allowed(tool.name)
                        actual_events.append(
                            sanitize_tool_event(
                                {
                                    "name": tool.name,
                                    "status": output.status,
                                    "query": query,
                                    "result_summary": output.message
                                    or "Policy evidence returned.",
                                },
                                settings=self.settings,
                            )
                        )
                    except (ToolAllowlistError, ToolSummarySanitizationError) as exc:
                        raise ToolFlowError from exc
            elif hasattr(tool, "last_tool_event"):
                event = getattr(tool, "last_tool_event", None)
                if (
                    isinstance(tool, GetClaimStatusTool)
                    and preflight_claim_event is not None
                ):
                    event = preflight_claim_event
                if event is not None:
                    had_actual_observation = True
                    if event.status == "failure":
                        had_tool_failure = True
                    try:
                        self._tool_allowlist.ensure_allowed(event.name)
                        actual_events.append(
                            sanitize_tool_event(
                                event.model_dump(),
                                settings=self.settings,
                            )
                        )
                    except (ToolAllowlistError, ToolSummarySanitizationError) as exc:
                        raise ToolFlowError from exc

        if had_tool_failure:
            raise ToolFlowError

        if not had_actual_observation:
            return draft.model_copy(update={"sources": [], "tool_calls": []})

        merged_sources = self._deduplicate(actual_sources)
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
