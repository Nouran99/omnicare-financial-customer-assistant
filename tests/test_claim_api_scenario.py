"""US-033 API-level claim-status journey tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_support_flow
from app.core.config import Settings
from app.flows.omnicare_support import OmniCareSupportFlow
from app.main import create_app
from app.models.draft import AssistantDraft
from app.models.safety import SafetyCheckResult
from app.services.claims_repository import ClaimsRepository
from app.tools.get_claim_status import GetClaimStatusTool


FIXTURE_PATH = Path(__file__).parents[1] / "data" / "mock_claims.json"


class ClaimStatusJourneyCrew:
    """Small Crew seam that executes the real claim-status tool for API tests."""

    def __init__(self, tool: GetClaimStatusTool, claim_id: str) -> None:
        self.tool = tool
        self.claim_id = claim_id
        self.calls = 0
        self.inputs: dict[str, Any] | None = None

    def kickoff(self, *, inputs: dict[str, Any]) -> AssistantDraft:
        self.calls += 1
        self.inputs = inputs
        output = self.tool.run(claim_id=self.claim_id)
        if output.status == "success":
            assert output.claim is not None
            response = f"Claim {output.claim.claim_id} is {output.claim.status}."
        else:
            response = output.message or "No claim was found for the supplied claim ID."
        return AssistantDraft(
            response=response,
            safety_result=SafetyCheckResult.allowed_result("Allowed"),
        )


def build_settings() -> Settings:
    return Settings(
        deepseek_model="deepseek-v4-flash",
        safety_system_prompt_patterns="ignore previous instructions,reveal the system prompt",
        draft_coverage_assertion_patterns="coverage,covers,covered,eligible,will pay,does not cover",
        draft_claim_success_patterns="claim submitted,claim has been submitted,submission successful,submitted successfully,confirmation id,confirmation number",
    )


def build_client(flow: OmniCareSupportFlow, settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_support_flow] = lambda: flow
    return TestClient(app)


@pytest.mark.parametrize(
    ("claim_id", "expected_status", "other_claim_id"),
    [
        ("CLM-8821", "Approved", "CLM-9014"),
        ("CLM-9014", "Under Review", "CLM-8821"),
    ],
)
def test_api_known_claim_status_uses_requested_record_only(
    claim_id: str,
    expected_status: str,
    other_claim_id: str,
) -> None:
    settings = build_settings()
    tool = GetClaimStatusTool(repository=ClaimsRepository(FIXTURE_PATH))
    crew = ClaimStatusJourneyCrew(tool, claim_id)
    client = build_client(
        OmniCareSupportFlow(crew=crew, tools=[tool], settings=settings),
        settings,
    )
    before = FIXTURE_PATH.read_bytes()

    response = client.post(
        "/api/v1/chat",
        headers={"X-Request-ID": f"us033-{claim_id}"},
        json={"user_id": "policyholder-1", "message": f"Check claim {claim_id}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == f"Claim {claim_id} is {expected_status}."
    assert expected_status in body["response"]
    assert other_claim_id not in response.text
    assert body["sources"] == []
    assert body["tool_calls"] == [
        {
            "name": "get_claim_status",
            "status": "success",
            "arguments": claim_id,
            "result_summary": f"Claim status: {expected_status}.",
        }
    ]
    assert response.headers["X-Request-ID"] == f"us033-{claim_id}"
    assert crew.calls == 1
    assert crew.inputs is not None
    assert crew.inputs["message"] == f"Check claim {claim_id}"
    assert FIXTURE_PATH.read_bytes() == before


def test_api_unknown_claim_returns_safe_not_found_and_does_not_mutate_fixture(
    tmp_path: Path,
) -> None:
    temporary_fixture = tmp_path / "claims.json"
    before = FIXTURE_PATH.read_bytes()
    temporary_fixture.write_bytes(before)
    settings = build_settings()
    tool = GetClaimStatusTool(repository=ClaimsRepository(temporary_fixture))
    crew = ClaimStatusJourneyCrew(tool, "CLM-UNKNOWN")
    client = build_client(
        OmniCareSupportFlow(crew=crew, tools=[tool], settings=settings),
        settings,
    )
    temporary_before = temporary_fixture.read_bytes()

    response = client.post(
        "/api/v1/chat",
        json={"user_id": "policyholder-1", "message": "Check claim CLM-UNKNOWN"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "No claim was found for the supplied claim ID."
    assert body["sources"] == []
    assert body["tool_calls"] == [
        {
            "name": "get_claim_status",
            "status": "not_found",
            "arguments": "CLM-UNKNOWN",
            "result_summary": "No claim matched the requested ID.",
        }
    ]
    assert "CLM-8821" not in response.text
    assert "CLM-9014" not in response.text
    assert temporary_fixture.read_bytes() == temporary_before
