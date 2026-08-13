"""Deterministic validation for structured Crew drafts."""

import re
from collections.abc import Mapping
from typing import Any, Tuple

from crewai.tasks.task_output import TaskOutput

from ..core.config import Settings, get_settings
from ..models.draft import AssistantDraft


class DraftValidationError(ValueError):
    """Safe validation failure with a bounded machine-readable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _normalized_patterns(configured: str) -> list[str]:
    return [
        " ".join(pattern.casefold().split())
        for pattern in configured.split(",")
        if " ".join(pattern.casefold().split())
    ]


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains_any(value: str, configured: str) -> bool:
    normalized = _normalized_text(value)
    return any(pattern in normalized for pattern in _normalized_patterns(configured))


def _has_successful_submit_event(
    draft: AssistantDraft,
    *,
    settings: Settings,
) -> bool:
    confirmation_pattern = re.compile(
        rf"{re.escape(settings.claim_id_prefix)}[0-9A-F]{{{settings.claim_id_random_hex_length}}}",
        re.IGNORECASE,
    )
    return any(
        event.name == "submit_claim"
        and event.status == "success"
        and confirmation_pattern.search(
            f"{event.arguments or ''} {event.result_summary or ''}"
        )
        for event in draft.tool_calls
    )


def validate_draft_structure(
    draft: AssistantDraft,
    *,
    settings: Settings | None = None,
) -> AssistantDraft:
    """Validate only rules that are safe before CrewAI executes tools."""

    resolved_settings = settings or get_settings()
    if not draft.safety_result.allowed and draft.tool_calls:
        raise DraftValidationError("blocked_draft_contains_tool_calls")

    if _contains_any(draft.response, resolved_settings.safety_system_prompt_patterns):
        raise DraftValidationError("hidden_instruction_disclosure")

    return draft


def validate_assistant_draft(
    draft: AssistantDraft,
    *,
    settings: Settings | None = None,
) -> AssistantDraft:
    """Validate deterministic citation, safety, and claim-success rules."""

    resolved_settings = settings or get_settings()
    validated = validate_draft_structure(draft, settings=resolved_settings)

    has_empty_policy_retrieval = any(
        event.name == "search_policy" and event.status != "success"
        for event in validated.tool_calls
    )
    has_coverage_assertion = _contains_any(
        validated.response,
        resolved_settings.draft_coverage_assertion_patterns,
    )
    has_explicit_limitation = _contains_any(
        validated.response,
        resolved_settings.draft_insufficient_information_patterns,
    )
    if has_coverage_assertion and not validated.sources and not has_explicit_limitation:
        raise DraftValidationError("coverage_assertion_requires_source")

    if has_empty_policy_retrieval and not validated.sources and not has_explicit_limitation:
        raise DraftValidationError("insufficient_information_required")

    if _contains_any(validated.response, resolved_settings.draft_claim_success_patterns):
        if not _has_successful_submit_event(validated, settings=resolved_settings):
            raise DraftValidationError("false_claim_success")

    return validated


def parse_task_output(
    task_output: TaskOutput | AssistantDraft | Mapping[str, Any] | str,
) -> AssistantDraft:
    """Parse a CrewAI task output without applying evidence-dependent rules yet."""

    raw: Any = task_output
    if isinstance(task_output, TaskOutput):
        raw = task_output.pydantic or task_output.json_dict or task_output.raw
    else:
        crew_pydantic = getattr(task_output, "pydantic", None)
        crew_json_dict = getattr(task_output, "json_dict", None)
        crew_raw = getattr(task_output, "raw", None)
        if crew_pydantic is not None:
            raw = crew_pydantic
        elif crew_json_dict is not None:
            raw = crew_json_dict
        elif crew_raw is not None:
            raw = crew_raw
    try:
        return raw if isinstance(raw, AssistantDraft) else AssistantDraft.model_validate(raw)
    except Exception as exc:
        raise DraftValidationError("malformed_draft") from exc


def validate_task_output(
    task_output: TaskOutput | AssistantDraft | Mapping[str, Any] | str,
    *,
    settings: Settings | None = None,
) -> AssistantDraft:
    """Parse and validate a CrewAI task output without exposing raw output details."""

    return validate_assistant_draft(
        parse_task_output(task_output),
        settings=settings,
    )


def support_request_guardrail(
    task_output: TaskOutput | AssistantDraft | Mapping[str, Any] | str,
) -> Tuple[bool, Any]:
    """CrewAI guardrail callback returning only typed output or a safe code."""

    try:
        draft = parse_task_output(task_output)
        return True, validate_draft_structure(draft)
    except DraftValidationError as exc:
        return False, f"draft_validation_failed:{exc.code}"
