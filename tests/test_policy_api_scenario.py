"""US-032 API-level policy journey tests with fake Crew and retrieval seams."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.api.routes import get_support_flow
from app.core.config import Settings
from app.flows.omnicare_support import OmniCareSupportFlow
from app.main import create_app
from app.models.api import ChatResponse
from app.models.draft import AssistantDraft
from app.models.safety import SafetyCheckResult
from app.tools.schemas import PolicyEvidenceOutput, SearchPolicyOutput


class FakeSearchTool:
    name = "search_policy"

    def __init__(self) -> None:
        self.last_output: SearchPolicyOutput | None = None

    def reset_observation(self) -> None:
        self.last_output = None


class FakeCrew:
    def __init__(self, draft: AssistantDraft, search_tool: FakeSearchTool, output: SearchPolicyOutput) -> None:
        self.draft = draft
        self.search_tool = search_tool
        self.output = output
        self.calls = 0

    def kickoff(self, *, inputs: dict[str, Any]) -> AssistantDraft:
        del inputs
        self.calls += 1
        self.search_tool.last_output = self.output
        return self.draft


def build_settings() -> Settings:
    return Settings(
        deepseek_model="deepseek-v4-flash",
        safety_system_prompt_patterns="ignore previous instructions,reveal the system prompt",
        draft_coverage_assertion_patterns="coverage,covers,covered,eligible,will pay,does not cover",
        draft_claim_success_patterns="claim submitted,claim has been submitted,submission successful,submitted successfully,confirmation id,confirmation number",
    )


def allowed() -> SafetyCheckResult:
    return SafetyCheckResult.allowed_result("Allowed")


def build_client(flow: OmniCareSupportFlow) -> TestClient:
    app = create_app(build_settings())
    app.dependency_overrides[get_support_flow] = lambda: flow
    return TestClient(app)


def test_api_policy_journey_returns_required_facts_and_section_citation() -> None:
    search_tool = FakeSearchTool()
    source = "sample_policy.md — Section 1: Home Water Damage Coverage"
    policy_output = SearchPolicyOutput(
        status="success",
        results=[
            PolicyEvidenceOutput(
                section_title="Home Water Damage Coverage",
                text=(
                    "Sudden pipe bursts are covered up to $25,000 with a $500 deductible. "
                    "Gradual leaks and floods are excluded."
                ),
                citation=source,
            )
        ],
    )
    draft = AssistantDraft(
        response=(
            "Sudden pipe-burst damage is covered up to $25,000 with a $500 deductible. "
            "Gradual leaks and floods are excluded."
        ),
        safety_result=allowed(),
    )
    crew = FakeCrew(draft, search_tool, policy_output)
    client = build_client(
        OmniCareSupportFlow(
            crew=crew,
            tools=[search_tool],
            settings=build_settings(),
        )
    )

    response = client.post(
        "/api/v1/chat",
        json={"user_id": "policyholder-1", "message": "Is sudden pipe-burst damage covered?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "$25,000" in body["response"]
    assert "$500" in body["response"]
    assert "gradual leaks" in body["response"].casefold()
    assert "floods" in body["response"].casefold()
    assert body["sources"] == [source]
    assert [event["name"] for event in body["tool_calls"]] == ["search_policy"]
    assert "get_claim_status" not in response.text
    assert "submit_claim" not in response.text
    assert crew.calls == 1


def test_api_unsupported_policy_question_does_not_invent_coverage() -> None:
    search_tool = FakeSearchTool()
    policy_output = SearchPolicyOutput(
        status="not_found",
        message="No sufficiently relevant policy evidence was found.",
    )
    draft = AssistantDraft(
        response="No sufficiently relevant policy evidence was found for this question.",
        safety_result=allowed(),
    )
    crew = FakeCrew(draft, search_tool, policy_output)
    client = build_client(
        OmniCareSupportFlow(
            crew=crew,
            tools=[search_tool],
            settings=build_settings(),
        )
    )

    response = client.post(
        "/api/v1/chat",
        json={"user_id": "policyholder-1", "message": "Does the policy cover earthquakes?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "$25,000" not in body["response"]
    assert "$500" not in body["response"]
    assert body["sources"] == []
    assert [event["name"] for event in body["tool_calls"]] == ["search_policy"]
    assert "claim" not in body["response"].casefold()
