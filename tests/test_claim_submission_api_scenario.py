"""US-034 API-level claim-submission journey tests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.routes import get_support_flow
from app.core.config import Settings
from app.flows.omnicare_support import OmniCareSupportFlow
from app.main import create_app
from app.models.draft import AssistantDraft
from app.models.safety import SafetyCheckResult
from app.services.claims_repository import AtomicClaimsPersistence, ClaimsRepository
from app.tools.submit_claim import SubmitClaimTool


CLAIM_ID_PATTERN = re.compile(r"^CLM-[0-9A-F]{8}$")


class ClaimSubmissionJourneyCrew:
    """Small Crew seam that executes the real submit_claim tool for API tests."""

    def __init__(self, tool: SubmitClaimTool, payload: dict[str, object]) -> None:
        self.tool = tool
        self.payload = payload
        self.calls = 0
        self.inputs: dict[str, Any] | None = None

    def kickoff(self, *, inputs: dict[str, Any]) -> AssistantDraft:
        self.calls += 1
        self.inputs = inputs
        output = self.tool.run(**self.payload)
        if output.status == "success":
            response = (
                f"Claim submitted successfully. Confirmation ID: {output.claim_id}. "
                f"Initial status: {output.claim_status}."
            )
        else:
            response = output.message or "The claim submission failed safely."
        return AssistantDraft(
            response=response,
            safety_result=SafetyCheckResult.allowed_result("Allowed"),
        )


class MissingFieldsCrew:
    """Return a deterministic follow-up without invoking the write tool."""

    def __init__(self) -> None:
        self.calls = 0

    def kickoff(self, *, inputs: dict[str, Any]) -> AssistantDraft:
        del inputs
        self.calls += 1
        return AssistantDraft(
            response=(
                "Before I can submit the claim, please provide the policy number, "
                "claim type, amount, and description."
            ),
            follow_up_question="Which required claim detail would you like to provide first?",
            safety_result=SafetyCheckResult.allowed_result("Allowed"),
        )


def build_settings(target: Path) -> Settings:
    return Settings(
        deepseek_model="deepseek-v4-flash",
        claims_file_path=str(target),
        claim_id_prefix="CLM-",
        claim_id_random_hex_length=8,
        claim_id_generation_attempts=5,
        initial_claim_status="Submitted",
        safety_system_prompt_patterns="ignore previous instructions,reveal the system prompt",
        draft_coverage_assertion_patterns="coverage,covers,covered,eligible,will pay,does not cover",
        draft_claim_success_patterns="claim submitted,claim has been submitted,submission successful,submitted successfully,confirmation id,confirmation number",
    )


def build_client(flow: OmniCareSupportFlow, settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_support_flow] = lambda: flow
    return TestClient(app)


def submission_payload() -> dict[str, object]:
    return {
        "policy_number": "POL-NEW",
        "claim_type": "Water Damage",
        "amount": 42.125,
        "description": "A sudden pipe burst damaged the kitchen.",
    }


def test_api_submission_appends_one_record_and_returns_confirmation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "claims.json"
    target.write_text("[]\n", encoding="utf-8")
    settings = build_settings(target)
    tool = SubmitClaimTool(
        persistence=AtomicClaimsPersistence(ClaimsRepository(target)),
        settings=settings,
        id_suffix_factory=lambda: "ABCDEF12",
    )
    crew = ClaimSubmissionJourneyCrew(tool, submission_payload())
    client = build_client(
        OmniCareSupportFlow(crew=crew, tools=[tool], settings=settings),
        settings,
    )
    before = target.read_bytes()

    response = client.post(
        "/api/v1/chat",
        headers={"X-Request-ID": "us034-submission"},
        json={
            "user_id": "policyholder-1",
            "message": (
                "Submit a claim for policy POL-NEW, claim type Water Damage, "
                "amount 42.125, and description: A sudden pipe burst damaged the kitchen."
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == (
        "Claim submitted successfully. Confirmation ID: CLM-ABCDEF12. "
        "Initial status: Submitted."
    )
    assert body["sources"] == []
    assert body["tool_calls"] == [
        {
            "name": "submit_claim",
            "status": "success",
            "arguments": None,
            "result_summary": "Claim submitted successfully.",
        }
    ]
    assert response.headers["X-Request-ID"] == "us034-submission"
    assert crew.calls == 1
    assert target.read_bytes() != before

    records = json.loads(target.read_text(encoding="utf-8"))
    assert len(records) == 1
    record = records[0]
    assert CLAIM_ID_PATTERN.fullmatch(record["claim_id"])
    assert record == {
        "claim_id": "CLM-ABCDEF12",
        "policy_number": "POL-NEW",
        "claim_type": "Water Damage",
        "amount": 42.13,
        "description": "A sudden pipe burst damaged the kitchen.",
        "status": "Submitted",
    }


def test_api_missing_fields_returns_follow_up_without_mutation(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    target.write_text("[]\n", encoding="utf-8")
    settings = build_settings(target)
    crew = MissingFieldsCrew()
    client = build_client(
        OmniCareSupportFlow(crew=crew, settings=settings),
        settings,
    )
    before = target.read_bytes()

    response = client.post(
        "/api/v1/chat",
        json={"user_id": "policyholder-1", "message": "Please submit a claim."},
    )

    assert response.status_code == 200
    body = response.json()
    assert "policy number" in body["response"].casefold()
    assert "claim type" in body["response"].casefold()
    assert "amount" in body["response"].casefold()
    assert "description" in body["response"].casefold()
    assert body["tool_calls"] == []
    assert body["sources"] == []
    assert target.read_bytes() == before
    assert crew.calls == 1
