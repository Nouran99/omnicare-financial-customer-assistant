"""Tests for the typed claims domain and supplied fixture."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.claims import ClaimSubmission, StoredClaim


FIXTURE_PATH = Path(__file__).parents[1] / "data" / "mock_claims.json"


def test_supplied_fixture_has_exact_records_and_validates() -> None:
    raw_records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert len(raw_records) == 2
    assert {record["claim_id"] for record in raw_records} == {"CLM-8821", "CLM-9014"}
    assert raw_records[0]["amount"] == 3500.00
    assert raw_records[1]["amount"] == 1200.00
    assert all(set(record) == {"claim_id", "policy_number", "claim_type", "status", "amount"} for record in raw_records)
    assert all(StoredClaim.model_validate(record).description is None for record in raw_records)


@pytest.mark.parametrize(
    "payload",
    [
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": 0, "description": "Burst"},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": -1, "description": "Burst"},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": math.nan, "description": "Burst"},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": math.inf, "description": "Burst"},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": "12.50", "description": "Burst"},
        {"policy_number": " ", "claim_type": "Water Damage", "amount": 10, "description": "Burst"},
        {"policy_number": "POL-1", "claim_type": " ", "amount": 10, "description": "Burst"},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": 10, "description": " "},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": 10},
        {"policy_number": "POL-1", "claim_type": "Water Damage", "amount": 10, "description": "Burst", "user_id": "user-1"},
    ],
)
def test_invalid_submissions_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises((ValidationError, TypeError)):
        ClaimSubmission.model_validate(payload)


def test_valid_submission_trims_text_rounds_amount_and_retains_description() -> None:
    submission = ClaimSubmission(
        policy_number=" POL-1092 ",
        claim_type=" Water Damage ",
        amount=123.456,
        description=" Pipe burst in kitchen ",
    )

    assert submission.policy_number == "POL-1092"
    assert submission.claim_type == "Water Damage"
    assert submission.amount == 123.46
    assert submission.description == "Pipe burst in kitchen"
    assert isinstance(submission.model_dump(mode="json")["amount"], float)


def test_amount_rounding_precision_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAIM_AMOUNT_DECIMAL_PLACES", "0")
    get_settings.cache_clear()
    try:
        submission = ClaimSubmission(
            policy_number="POL-1",
            claim_type="Water Damage",
            amount=12.5,
            description="Rounded according to runtime configuration",
        )
    finally:
        get_settings.cache_clear()

    assert submission.amount == 13.0


def test_stored_claim_accepts_original_records_and_new_description() -> None:
    claim = StoredClaim(
        claim_id="CLM-1000",
        policy_number="POL-1092",
        claim_type="Water Damage",
        status="Submitted",
        amount=99.999,
        description="Validated description",
    )

    assert claim.amount == 100.0
    assert claim.description == "Validated description"
