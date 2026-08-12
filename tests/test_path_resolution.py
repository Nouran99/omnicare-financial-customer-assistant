"""Tests for configuration-driven runtime path resolution."""

from __future__ import annotations

from pathlib import Path

from app.core.paths import resolve_configured_path
from app.services.claims_repository import ClaimsRepository
from app.services.policy_loader import PolicyDocumentLoader


def test_parent_data_path_resolves_from_repository_root(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    data_dir = repository_root / "data"
    data_dir.mkdir(parents=True)
    policy_path = data_dir / "sample_policy.md"
    policy_path.write_text("## Section 1: Coverage\nCovered content.\n", encoding="utf-8")

    resolved = resolve_configured_path(
        "../data/sample_policy.md",
        base_dir=repository_root,
        root_dir=repository_root,
    )

    assert resolved == policy_path
    assert PolicyDocumentLoader().load_file(resolved)[0].section_title == "Coverage"


def test_claims_repository_resolves_configured_fixture_from_repository_root() -> None:
    repository = ClaimsRepository("../data/mock_claims.json")

    claims = repository.load_all()

    assert [claim.claim_id for claim in claims] == ["CLM-8821", "CLM-9014"]


def test_relative_data_path_resolves_from_backend_working_directory(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    backend_dir = repository_root / "backend"
    data_dir = repository_root / "data"
    backend_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    policy_path = data_dir / "sample_policy.md"
    policy_path.write_text("## Section 1: Coverage\nCovered content.\n", encoding="utf-8")

    resolved = resolve_configured_path(
        "../data/sample_policy.md",
        base_dir=backend_dir,
        root_dir=repository_root,
    )

    assert resolved == policy_path
