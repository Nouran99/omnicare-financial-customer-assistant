"""Tests for the typed CrewAI tool schemas introduced by US-022."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.claims import StoredClaim
from app.tools.schemas import (
    ClaimSummaryOutput,
    GetClaimStatusInput,
    GetClaimStatusOutput,
    GetClaimStatusToolDefinition,
    PolicyEvidenceOutput,
    SearchPolicyInput,
    SearchPolicyOutput,
    SearchPolicyToolDefinition,
    SubmitClaimInput,
    SubmitClaimOutput,
    SubmitClaimToolDefinition,
)


def test_tool_definitions_have_unique_stable_names_and_explicit_schemas() -> None:
    definitions = [
        SearchPolicyToolDefinition(),
        GetClaimStatusToolDefinition(),
        SubmitClaimToolDefinition(),
    ]

    assert [definition.name for definition in definitions] == [
        "search_policy",
        "get_claim_status",
        "submit_claim",
    ]
    assert len({definition.name for definition in definitions}) == 3
    assert all(definition.description.strip() for definition in definitions)
    assert all(definition.args_schema.model_fields for definition in definitions)
    assert all(definition.result_schema is not None for definition in definitions)
    assert all(definition.to_structured_tool().name == definition.name for definition in definitions)


def test_search_policy_input_is_bounded_and_forbids_paths_or_extra_fields() -> None:
    assert SearchPolicyInput(query=" Is water damage covered? ").query == "Is water damage covered?"

    for payload in (
        {},
        {"query": " "},
        {"query": "x", "path": "/etc/passwd"},
        {"query": 123},
    ):
        with pytest.raises(ValidationError):
            SearchPolicyInput.model_validate(payload)


def test_claim_inputs_validate_required_fields_types_and_extras() -> None:
    valid_status = GetClaimStatusInput(claim_id="CLM-8821")
    valid_submission = SubmitClaimInput(
        policy_number="POL-1",
        claim_type="Water Damage",
        amount=10.125,
        description="Pipe burst",
    )
    assert valid_status.claim_id == "CLM-8821"
    assert valid_submission.amount == 10.125

    invalid_status = ({}, {"claim_id": " "}, {"claim_id": "CLM-1", "path": "/tmp"})
    for payload in invalid_status:
        with pytest.raises(ValidationError):
            GetClaimStatusInput.model_validate(payload)

    for payload in (
        {"policy_number": "POL-1", "claim_type": "Water Damage", "description": "x"},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": 0, "description": "x"},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": 1, "description": "x", "path": "/tmp"},
    ):
        with pytest.raises(ValidationError):
            SubmitClaimInput.model_validate(payload)


def test_outputs_distinguish_success_not_found_and_failure() -> None:
    evidence = PolicyEvidenceOutput(
        section_title="Home Water Damage Coverage",
        text="Sudden pipe bursts are covered.",
        citation="sample_policy.md — Section 1: Home Water Damage Coverage",
    )
    policy_success = SearchPolicyOutput(status="success", results=[evidence])
    policy_not_found = SearchPolicyOutput(status="not_found", message="No evidence found.")
    policy_failure = SearchPolicyOutput(status="failure", message="Retrieval failed.")

    claim = StoredClaim(
        claim_id="CLM-8821",
        policy_number="POL-1092",
        claim_type="Water Damage",
        status="Approved",
        amount=3500,
    )
    claim_success = GetClaimStatusOutput(
        status="success", claim=ClaimSummaryOutput.from_claim(claim)
    )
    claim_not_found = GetClaimStatusOutput(
        status="not_found", claim_id="CLM-UNKNOWN", message="Claim not found."
    )
    claim_failure = GetClaimStatusOutput(status="failure", message="Lookup failed.")
    submit_success = SubmitClaimOutput(
        status="success",
        claim_id="CLM-1000",
        claim_status="Submitted",
        message="Claim submitted.",
    )
    submit_failure = SubmitClaimOutput(status="failure", message="Submission failed.")

    assert policy_success.status == "success"
    assert policy_not_found.results == []
    assert policy_failure.results == []
    assert claim_success.claim.claim_id == "CLM-8821"
    assert claim_not_found.claim_id == "CLM-UNKNOWN"
    assert claim_failure.claim is None
    assert submit_success.claim_status == "Submitted"
    assert submit_failure.claim_id is None

    invalid_outputs = (
        lambda: SearchPolicyOutput(status="success"),
        lambda: GetClaimStatusOutput(status="success"),
        lambda: SubmitClaimOutput(status="success", message="missing claim details"),
        lambda: SubmitClaimOutput(status="failure", claim_id="CLM-1", message="unsafe"),
    )
    for factory in invalid_outputs:
        with pytest.raises(ValidationError):
            factory()


def test_json_schemas_are_bounded_and_exclude_arbitrary_filesystem_access() -> None:
    schemas = [
        SearchPolicyInput.model_json_schema(),
        GetClaimStatusInput.model_json_schema(),
        SubmitClaimInput.model_json_schema(),
        SearchPolicyOutput.model_json_schema(),
        GetClaimStatusOutput.model_json_schema(),
        SubmitClaimOutput.model_json_schema(),
    ]
    assert all("path" not in schema.get("properties", {}) for schema in schemas)
    assert all(schema.get("additionalProperties") is False for schema in schemas)
