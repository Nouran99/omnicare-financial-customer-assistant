"""CrewAI-compatible read-only claim-status tool for US-024."""

from __future__ import annotations

import logging
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, PrivateAttr

from ..core.logging import log_tool_event
from ..core.config import Settings, get_settings
from ..models.claims import (
    ClaimStatusFound,
    ClaimStatusLookupRequest,
    ClaimToolEvent,
)
from ..services.claims_repository import ClaimsRepository, ClaimsRepositoryError
logger = logging.getLogger("omnicare.tools.get_claim_status")


from .schemas import (
    GetClaimStatusInput,
    GetClaimStatusOutput,
    ClaimSummaryOutput,
)


class GetClaimStatusTool(BaseTool):
    """Look up exactly one claim and return only its safe summary."""

    name: str = "get_claim_status"
    description: str = (
        "Look up one claim by its exact claim ID and return its stored status. "
        "Returns only the requested claim or a safe not-found outcome."
    )
    args_schema: type[BaseModel] = GetClaimStatusInput
    result_schema: type[BaseModel] = GetClaimStatusOutput

    _repository: ClaimsRepository | None = PrivateAttr(default=None)
    _settings: Settings = PrivateAttr()
    _last_event: ClaimToolEvent | None = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        repository: ClaimsRepository | None = None,
        settings: Settings | None = None,
        **data: Any,
    ) -> None:
        super().__init__(**data)
        self._repository = repository
        self._settings = settings or get_settings()

    @property
    def last_tool_event(self) -> ClaimToolEvent | None:
        """Return the latest safe operation record for later response composition."""

        return self._last_event

    def reset_observation(self) -> None:
        """Clear the latest event before a new Flow request."""

        self._last_event = None

    def _run(self, claim_id: str) -> GetClaimStatusOutput:
        try:
            lookup = ClaimStatusLookupRequest(claim_id=claim_id)
            result = self._get_repository().find_by_claim_id(lookup)
        except ClaimsRepositoryError:
            return self._failure("Claim status is temporarily unavailable.")
        except Exception:  # pragma: no cover - defensive tool boundary
            return self._failure("Claim status lookup failed safely.")

        if isinstance(result, ClaimStatusFound):
            output = GetClaimStatusOutput(
                status="success",
                claim=ClaimSummaryOutput.from_claim(result.claim),
                message="Requested claim status returned.",
            )
            self._record_event(
                "success",
                "Requested claim status returned.",
                claim_id=result.claim.claim_id,
                claim_status=result.claim.status,
            )
            return output

        output = GetClaimStatusOutput(
            status="not_found",
            claim_id=result.claim_id,
            message="No claim was found for the supplied claim ID.",
        )
        self._record_event(
            "not_found",
            "No claim matched the requested ID.",
            claim_id=result.claim_id,
        )
        return output

    def _get_repository(self) -> ClaimsRepository:
        if self._repository is None:
            self._repository = ClaimsRepository(self._settings.claims_file_path)
        return self._repository

    def _failure(self, message: str) -> GetClaimStatusOutput:
        self._record_event("failure", message)
        return GetClaimStatusOutput(status="failure", message=message)

    def _record_event(
        self,
        status: str,
        result_summary: str,
        *,
        claim_id: str | None = None,
        claim_status: str | None = None,
    ) -> None:
        self._last_event = ClaimToolEvent(
            name=self.name,
            status=status,
            claim_id=claim_id,
            claim_status=claim_status,
            result_summary=result_summary,
        )
        log_tool_event(
            logger=logger,
            request_id=None,
            tool_name=self.name,
            status=status,
        )
