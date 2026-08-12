"""Tests for controlled claims reads and atomic persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.claims import ClaimStatusFound, ClaimStatusNotFound, StoredClaim
from app.services.claims_repository import (
    AtomicClaimsPersistence,
    ClaimsFixtureInvalidError,
    ClaimsFixtureMissingError,
    ClaimsPersistenceError,
    ClaimsRepository,
)


FIXTURE_PATH = Path(__file__).parents[1] / "data" / "mock_claims.json"


def test_known_claim_ids_return_only_the_requested_record() -> None:
    repository = ClaimsRepository(FIXTURE_PATH)

    first = repository.find_by_claim_id(" CLM-8821 ")
    second = repository.find_by_claim_id("CLM-9014")

    assert isinstance(first, ClaimStatusFound)
    assert first.claim.claim_id == "CLM-8821"
    assert first.claim.status == "Approved"
    assert first.claim.amount == 3500.0
    assert isinstance(second, ClaimStatusFound)
    assert second.claim.claim_id == "CLM-9014"
    assert second.claim.status == "Under Review"


def test_unknown_claim_id_returns_typed_not_found_without_mutation(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    target.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    before = target.read_bytes()
    repository = ClaimsRepository(target)

    result = repository.find_by_claim_id("CLM-UNKNOWN")

    assert isinstance(result, ClaimStatusNotFound)
    assert result.claim_id == "CLM-UNKNOWN"
    assert target.read_bytes() == before


@pytest.mark.parametrize(
    "file_content,error_type",
    [
        (None, ClaimsFixtureMissingError),
        ("{not-json", ClaimsFixtureInvalidError),
        (json.dumps({"claim_id": "CLM-1"}), ClaimsFixtureInvalidError),
        (json.dumps([{"claim_id": "CLM-1", "amount": "not-number"}]), ClaimsFixtureInvalidError),
    ],
)
def test_missing_or_invalid_fixtures_use_controlled_errors(
    tmp_path: Path, file_content: str | None, error_type: type[Exception]
) -> None:
    target = tmp_path / "claims.json"
    if file_content is not None:
        target.write_text(file_content, encoding="utf-8")

    with pytest.raises(error_type) as error:
        ClaimsRepository(target).load_all()

    assert str(target) not in str(error.value)


def _new_claim(claim_id: str, amount: float = 42.125) -> StoredClaim:
    return StoredClaim(
        claim_id=claim_id,
        policy_number="POL-NEW",
        claim_type="Water Damage",
        status="Submitted",
        amount=amount,
        description="Newly submitted claim description",
    )


def test_atomic_append_adds_exactly_one_valid_record_and_retains_description(
    tmp_path: Path,
) -> None:
    target = tmp_path / "claims.json"
    target.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    repository = ClaimsRepository(target)
    persistence = AtomicClaimsPersistence(repository)

    result = persistence.append(_new_claim("CLM-1000"))
    records = json.loads(target.read_text(encoding="utf-8"))

    assert result.success is True
    assert result.claim.claim_id == "CLM-1000"
    assert len(records) == 3
    assert records[-1]["amount"] == 42.13
    assert records[-1]["description"] == "Newly submitted claim description"
    assert len(repository.load_all()) == 3


def test_repeated_appends_are_unique_and_duplicate_id_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    target.write_text("[]\n", encoding="utf-8")
    persistence = AtomicClaimsPersistence(ClaimsRepository(target))

    persistence.append(_new_claim("CLM-1000"))
    persistence.append(_new_claim("CLM-1001"))

    with pytest.raises(ClaimsPersistenceError):
        persistence.append(_new_claim("CLM-1001"))

    assert len(json.loads(target.read_text(encoding="utf-8"))) == 2


def test_persistence_rejects_unvalidated_object_before_file_access(tmp_path: Path) -> None:
    target = tmp_path / "claims.json"
    target.write_text("[]\n", encoding="utf-8")
    persistence = AtomicClaimsPersistence(ClaimsRepository(target))

    with pytest.raises(TypeError):
        persistence.append({"claim_id": "CLM-1"})  # type: ignore[arg-type]

    assert target.read_text(encoding="utf-8") == "[]\n"


def test_serialization_failure_preserves_original_valid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "claims.json"
    original = FIXTURE_PATH.read_bytes()
    target.write_bytes(original)
    persistence = AtomicClaimsPersistence(ClaimsRepository(target))

    def fail_dump(*args: object, **kwargs: object) -> None:
        raise TypeError("simulated serialization failure")

    monkeypatch.setattr("app.services.claims_repository.json.dump", fail_dump)

    with pytest.raises(ClaimsPersistenceError):
        persistence.append(_new_claim("CLM-1000"))

    assert target.read_bytes() == original
    assert isinstance(json.loads(target.read_text(encoding="utf-8")), list)
    assert list(tmp_path.glob(".*.tmp")) == []


def test_replacement_failure_preserves_original_valid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "claims.json"
    original = FIXTURE_PATH.read_bytes()
    target.write_bytes(original)
    persistence = AtomicClaimsPersistence(ClaimsRepository(target))

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr("app.services.claims_repository.os.replace", fail_replace)

    with pytest.raises(ClaimsPersistenceError):
        persistence.append(_new_claim("CLM-1000"))

    assert target.read_bytes() == original
    assert isinstance(json.loads(target.read_text(encoding="utf-8")), list)
    assert list(tmp_path.glob(".*.tmp")) == []
