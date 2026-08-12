"""Tests for the US-025 atomic submit_claim tool."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.claims_repository import (
    AtomicClaimsPersistence,
    ClaimsPersistenceError,
    ClaimsRepository,
)
from app.tools.submit_claim import SubmitClaimTool


ID_PATTERN = re.compile(r"^CLM-[0-9A-F]{8}$")


def build_tool(
    target: Path,
    *,
    suffixes: list[str] | None = None,
    persistence: AtomicClaimsPersistence | None = None,
) -> SubmitClaimTool:
    target.write_text("[]\n", encoding="utf-8")
    repository = ClaimsRepository(target)
    settings = Settings(
        claims_file_path=str(target),
        claim_id_prefix="CLM-",
        claim_id_random_hex_length=8,
        claim_id_generation_attempts=5,
        initial_claim_status="Submitted",
    )
    suffix_values = iter(suffixes or ["ABCDEF12"])
    return SubmitClaimTool(
        persistence=persistence or AtomicClaimsPersistence(repository),
        settings=settings,
        id_suffix_factory=lambda: next(suffix_values),
    )


def submission_payload() -> dict[str, object]:
    return {
        "policy_number": "POL-NEW",
        "claim_type": "Water Damage",
        "amount": 42.125,
        "description": "A sudden pipe burst damaged the kitchen.",
    }


def test_valid_submission_appends_one_record_and_returns_confirmation_id(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    tool = build_tool(target)

    result = tool.run(**submission_payload())
    records = json.loads(target.read_text(encoding="utf-8"))

    assert result.status == "success"
    assert result.claim_id is not None
    assert ID_PATTERN.fullmatch(result.claim_id)
    assert result.claim_status == "Submitted"
    assert len(records) == 1
    assert records[0]["claim_id"] == result.claim_id
    assert records[0]["amount"] == 42.13
    assert records[0]["description"] == submission_payload()["description"]
    assert records[0]["status"] == "Submitted"
    assert tool.last_tool_event is not None
    assert tool.last_tool_event.status == "success"


def test_repeated_successful_calls_are_idempotent_until_observation_reset(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    tool = build_tool(target, suffixes=["ABCDEF12", "ABCDEF13"])

    first = tool.run(**submission_payload())
    repeated = tool.run(
        policy_number="POL-SECOND",
        claim_type="Personal Property",
        amount=99,
        description="A second request in the same Crew execution.",
    )

    records = json.loads(target.read_text(encoding="utf-8"))
    assert first.status == "success"
    assert repeated == first
    assert len(records) == 1

    tool.reset_observation()
    after_reset = tool.run(
        policy_number="POL-SECOND",
        claim_type="Personal Property",
        amount=99,
        description="A second request after the Flow reset.",
    )
    records_after_reset = json.loads(target.read_text(encoding="utf-8"))
    assert after_reset.status == "success"
    assert after_reset.claim_id != first.claim_id
    assert len(records_after_reset) == 2


def test_invalid_missing_field_or_amount_does_not_mutate_fixture(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    tool = build_tool(target)
    before = target.read_bytes()

    with pytest.raises(ValueError):
        tool.run(
            policy_number="POL-NEW",
            claim_type="Water Damage",
            amount=42,
        )
    with pytest.raises(ValueError):
        tool.run(
            policy_number="POL-NEW",
            claim_type="Water Damage",
            amount=0,
            description="Invalid amount",
        )
    with pytest.raises(ValueError):
        tool.run(**submission_payload(), path="/tmp/claims.json")

    assert target.read_bytes() == before
    assert json.loads(target.read_text(encoding="utf-8")) == []


def test_collision_is_skipped_and_generated_id_remains_unique(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    target.write_text(
        json.dumps(
            [
                {
                    "claim_id": "CLM-AAAAAAAA",
                    "policy_number": "POL-OLD",
                    "claim_type": "Water Damage",
                    "status": "Approved",
                    "amount": 10,
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    repository = ClaimsRepository(target)
    settings = Settings(
        claims_file_path=str(target),
        claim_id_prefix="CLM-",
        claim_id_random_hex_length=8,
        claim_id_generation_attempts=5,
        initial_claim_status="Submitted",
    )
    suffixes = iter(["AAAAAAAA", "BBBBBBBB"])
    tool = SubmitClaimTool(
        persistence=AtomicClaimsPersistence(repository),
        settings=settings,
        id_suffix_factory=lambda: next(suffixes),
    )

    result = tool.run(**submission_payload())
    records = json.loads(target.read_text(encoding="utf-8"))

    assert result.status == "success"
    assert result.claim_id == "CLM-BBBBBBBB"
    assert len(records) == 2
    assert len({record["claim_id"] for record in records}) == 2


class FailingPersistence:
    def __init__(self, repository: ClaimsRepository) -> None:
        self.repository = repository

    def append(self, claim: object) -> object:
        raise ClaimsPersistenceError


def test_persistence_failure_cannot_return_success_or_mutate_fixture(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    target.write_text("[]\n", encoding="utf-8")
    repository = ClaimsRepository(target)
    tool = SubmitClaimTool(
        persistence=FailingPersistence(repository),  # type: ignore[arg-type]
        settings=Settings(claims_file_path=str(target)),
        id_suffix_factory=lambda: "ABCDEF12",
    )
    before = target.read_bytes()

    result = tool.run(**submission_payload())

    assert result.status == "failure"
    assert result.claim_id is None
    assert result.message == "The claim could not be persisted safely."
    assert target.read_bytes() == before
    assert tool.last_tool_event is not None
    assert tool.last_tool_event.status == "failure"


def test_exhausted_invalid_id_generation_fails_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    tool = build_tool(target, suffixes=["too-short"] * 5)
    before = target.read_bytes()

    result = tool.run(**submission_payload())

    assert result.status == "failure"
    assert target.read_bytes() == before
