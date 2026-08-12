"""CrewAI-compatible validated claim-submission tool for US-025."""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Callable
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, PrivateAttr

from ..core.config import Settings, get_settings
from ..core.logging import log_tool_event
from ..models.claims import ClaimSubmission, ClaimToolEvent, StoredClaim
from ..services.claims_repository import (
    AtomicClaimsPersistence,
    ClaimsPersistenceError,
)
from .schemas import SubmitClaimInput, SubmitClaimOutput

logger = logging.getLogger("omnicare.tools.submit_claim")


class SubmitClaimTool(BaseTool):
    """Validate and atomically append one new claim without model-controlled IDs."""

    name: str = "submit_claim"
    description: str = (
        "Validate and submit a new claim using policy number, claim type, amount, "
        "and description. Returns a confirmation ID only after atomic persistence succeeds."
    )
    args_schema: type[BaseModel] = SubmitClaimInput
    result_schema: type[BaseModel] = SubmitClaimOutput

    _persistence: AtomicClaimsPersistence | None = PrivateAttr(default=None)
    _settings: Settings = PrivateAttr()
    _id_suffix_factory: Callable[[], str] = PrivateAttr()
    _last_event: ClaimToolEvent | None = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        persistence: AtomicClaimsPersistence | None = None,
        settings: Settings | None = None,
        id_suffix_factory: Callable[[], str] | None = None,
        **data: Any,
    ) -> None:
        super().__init__(**data)
        self._persistence = persistence
        self._settings = settings or get_settings()
        self._id_suffix_factory = id_suffix_factory or (
            lambda: secrets.token_hex(
                (self._settings.claim_id_random_hex_length + 1) // 2
            )[: self._settings.claim_id_random_hex_length].upper()
        )

    @property
    def last_tool_event(self) -> ClaimToolEvent | None:
        """Return the latest safe operation record for later response composition."""

        return self._last_event

    def _run(
        self,
        policy_number: str,
        claim_type: str,
        amount: float,
        description: str,
    ) -> SubmitClaimOutput:
        try:
            submission = ClaimSubmission(
                policy_number=policy_number,
                claim_type=claim_type,
                amount=amount,
                description=description,
            )
            persistence = self._get_persistence()
            claim_id = self._generate_unique_claim_id(persistence)
            claim = StoredClaim(
                claim_id=claim_id,
                policy_number=submission.policy_number,
                claim_type=submission.claim_type,
                amount=submission.amount,
                description=submission.description,
                status=self._settings.initial_claim_status,
            )
            result = persistence.append(claim)
        except ClaimsPersistenceError:
            return self._failure("The claim could not be persisted safely.")
        except Exception:  # pragma: no cover - defensive write boundary
            return self._failure("The claim submission failed safely.")

        self._record_event("success", "Claim submitted successfully.")
        return SubmitClaimOutput(
            status="success",
            claim_id=result.claim.claim_id,
            claim_status=result.claim.status,
            message="Claim submitted successfully.",
        )

    def _get_persistence(self) -> AtomicClaimsPersistence:
        if self._persistence is None:
            from ..services.claims_repository import ClaimsRepository

            self._persistence = AtomicClaimsPersistence(
                ClaimsRepository(self._settings.claims_file_path)
            )
        return self._persistence

    def _generate_unique_claim_id(self, persistence: AtomicClaimsPersistence) -> str:
        repository = persistence.repository
        existing_ids = {claim.claim_id for claim in repository.load_all()}
        pattern = re.compile(
            rf"^{re.escape(self._settings.claim_id_prefix)}"
            rf"[0-9A-F]{{{self._settings.claim_id_random_hex_length}}}$"
        )
        for _ in range(self._settings.claim_id_generation_attempts):
            suffix = self._id_suffix_factory().strip().upper()
            if len(suffix) != self._settings.claim_id_random_hex_length:
                continue
            if not re.fullmatch(r"[0-9A-F]+", suffix):
                continue
            claim_id = f"{self._settings.claim_id_prefix}{suffix}"
            if pattern.fullmatch(claim_id) and claim_id not in existing_ids:
                return claim_id
        raise ClaimsPersistenceError

    def _failure(self, message: str) -> SubmitClaimOutput:
        self._record_event("failure", message)
        return SubmitClaimOutput(status="failure", message=message)

    def _record_event(self, status: str, result_summary: str) -> None:
        self._last_event = ClaimToolEvent(
            name=self.name,
            status=status,
            result_summary=result_summary,
        )
        log_tool_event(
            logger=logger,
            request_id=None,
            tool_name=self.name,
            status=status,
        )
