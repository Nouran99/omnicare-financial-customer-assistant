"""Claims fixture access with controlled reads and atomic local writes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from ..models.claims import (
    ClaimPersistenceResult,
    ClaimStatusFound,
    ClaimStatusLookupRequest,
    ClaimStatusNotFound,
    ClaimStatusResult,
    StoredClaim,
)


class ClaimsRepositoryError(Exception):
    """Base error for controlled claims-fixture failures."""

    public_detail = "The claims fixture could not be accessed."


class ClaimsFixtureMissingError(ClaimsRepositoryError):
    """The configured claims fixture does not exist."""

    public_detail = "The claims fixture is unavailable."


class ClaimsFixtureInvalidError(ClaimsRepositoryError):
    """The claims fixture is not valid JSON or does not match its schema."""

    public_detail = "The claims fixture is invalid."


class ClaimsPersistenceError(ClaimsRepositoryError):
    """An atomic replacement could not be completed."""

    public_detail = "The claim could not be persisted."


class DuplicateClaimError(ClaimsPersistenceError):
    """A validated record would reuse an existing claim ID."""

    public_detail = "The claim could not be persisted because its ID already exists."


def _load_claims(path: Path) -> list[StoredClaim]:
    try:
        with path.open("r", encoding="utf-8") as file:
            raw_claims = json.load(file)
    except FileNotFoundError as exc:
        raise ClaimsFixtureMissingError from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ClaimsFixtureInvalidError from exc

    if not isinstance(raw_claims, list):
        raise ClaimsFixtureInvalidError

    try:
        return [StoredClaim.model_validate(record) for record in raw_claims]
    except (TypeError, ValidationError) as exc:
        raise ClaimsFixtureInvalidError from exc


class ClaimsRepository:
    """Read-only exact-lookup repository over the configured claims fixture."""

    def __init__(self, claims_path: str | Path) -> None:
        self._claims_path = Path(claims_path)

    @property
    def claims_path(self) -> Path:
        """Return the configured fixture path for trusted persistence internals."""

        return self._claims_path

    def load_all(self) -> list[StoredClaim]:
        """Load and validate all records without exposing raw JSON objects."""

        return _load_claims(self._claims_path)

    def find_by_claim_id(
        self, lookup: ClaimStatusLookupRequest | str
    ) -> ClaimStatusResult:
        """Return only the requested record or a typed not-found result."""

        request = (
            lookup
            if isinstance(lookup, ClaimStatusLookupRequest)
            else ClaimStatusLookupRequest(claim_id=lookup)
        )
        for claim in self.load_all():
            if claim.claim_id == request.claim_id:
                return ClaimStatusFound(claim=claim)
        return ClaimStatusNotFound(claim_id=request.claim_id)


class AtomicClaimsPersistence:
    """Append validated claims through same-directory temporary-file replacement."""

    def __init__(self, repository: ClaimsRepository) -> None:
        self._repository = repository
        self._lock = RLock()

    def append(self, claim: StoredClaim) -> ClaimPersistenceResult:
        """Append one validated claim and return success only after replacement."""

        if not isinstance(claim, StoredClaim):
            raise TypeError("append requires a validated StoredClaim")

        with self._lock:
            current_claims = self._repository.load_all()
            if any(existing.claim_id == claim.claim_id for existing in current_claims):
                raise DuplicateClaimError

            updated_claims = [*current_claims, claim]
            self._atomic_replace(updated_claims)
            return ClaimPersistenceResult(claim=claim)

    def _atomic_replace(self, claims: list[StoredClaim]) -> None:
        target = self._repository.claims_path
        parent = target.parent
        temporary_path: Path | None = None
        try:
            parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                payload = [claim.model_dump(mode="json", exclude_none=True) for claim in claims]
                json.dump(payload, temporary_file, ensure_ascii=False, indent=2, allow_nan=False)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, target)
            temporary_path = None
        except (OSError, TypeError, ValueError) as exc:
            raise ClaimsPersistenceError from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
