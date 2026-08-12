"""CrewAI task definition for US-029 structured support output."""

from __future__ import annotations

from crewai import Agent, Task

from ..core.config import Settings, get_settings
from ..models.draft import AssistantDraft
from ..services.draft_validator import support_request_guardrail


def support_request_task(
    agent: Agent,
    *,
    settings: Settings | None = None,
) -> Task:
    """Build the one structured support task without starting a provider call."""

    resolved_settings = settings or get_settings()
    return Task(
        description=(
            f"{resolved_settings.crew_task_description}\n\n"
            f"{resolved_settings.crew_task_request_context_template}"
        ),
        expected_output=resolved_settings.crew_task_expected_output,
        agent=agent,
        output_pydantic=AssistantDraft,
        guardrail=support_request_guardrail,
        guardrail_max_retries=1,
    )
