"""Tests for the US-024 read-only get_claim_status tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.claims_repository import ClaimsRepository
from app.tools.get_claim_status import GetClaimStatusTool


FIXTURE_PATH = Path(__file__).parents[1] / "data" / "mock_claims.json"


def build_tool() -> GetClaimStatusTool:
    return GetClaimStatusTool(repository=ClaimsRepository(FIXTURE_PATH))


def test_known_claim_ids_return_only_the_requested_safe_summary() -> None:
    tool = build_tool()

    approved = tool.run(claim_id=" CLM-8821 ")
    under_review = tool.run(claim_id="CLM-9014")

    assert approved.status == "success"
    assert approved.claim is not None
    assert approved.claim.claim_id == "CLM-8821"
    assert approved.claim.status == "Approved"
    assert approved.claim.policy_number == "POL-1092"
    assert under_review.status == "success"
    assert under_review.claim is not None
    assert under_review.claim.claim_id == "CLM-9014"
    assert under_review.claim.status == "Under Review"
    assert under_review.claim.policy_number == "POL-3341"
    assert not hasattr(approved.claim, "description")


def test_unknown_claim_id_returns_not_found_without_exception_leak() -> None:
    tool = build_tool()

    result = tool.run(claim_id="CLM-UNKNOWN")

    assert result.status == "not_found"
    assert result.claim is None
    assert result.claim_id == "CLM-UNKNOWN"
    assert result.message == "No claim was found for the supplied claim ID."
    assert tool.last_tool_event is not None
    assert tool.last_tool_event.status == "not_found"


def test_blank_claim_id_is_rejected_before_repository_access() -> None:
    tool = build_tool()

    with pytest.raises(ValueError):
        tool.run(claim_id=" ")
    assert tool.last_tool_event is None


def test_claim_status_tool_is_read_only_and_records_safe_operation_events() -> None:
    before = FIXTURE_PATH.read_bytes()
    tool = build_tool()

    result = tool.run(claim_id="CLM-8821")

    after = FIXTURE_PATH.read_bytes()
    assert result.status == "success"
    assert before == after
    assert tool.last_tool_event is not None
    assert tool.last_tool_event.name == "get_claim_status"
    assert tool.last_tool_event.status == "success"
    assert "CLM-8821" not in (tool.last_tool_event.result_summary or "")


def test_invalid_fixture_returns_safe_failure(tmp_path: Path) -> None:
    invalid_fixture = tmp_path / "claims.json"
    invalid_fixture.write_text("not-json", encoding="utf-8")
    tool = GetClaimStatusTool(repository=ClaimsRepository(invalid_fixture))

    result = tool.run(claim_id="CLM-8821")

    assert result.status == "failure"
    assert result.claim is None
    assert result.message == "Claim status is temporarily unavailable."
