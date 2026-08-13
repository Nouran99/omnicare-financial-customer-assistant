"""Validate and normalize provider-generated business-tool arguments."""

from __future__ import annotations

import json
import math
from typing import Any

from pydantic import BaseModel, ValidationError

from ..core.config import Settings, get_settings
from ..core.errors import ProviderError
from ..providers.deepseek import ProviderToolCall
from ..tools.schemas import GetClaimStatusInput, SearchPolicyInput, SubmitClaimInput
from .tool_allowlist import ToolAllowlist, ToolAllowlistError


class ToolArgumentValidationError(ProviderError):
    """Safe validation failure raised before a provider tool can execute."""

    public_detail = "The assistant generated an invalid tool request."


class ProviderToolArgumentValidator:
    """Validate provider JSON against a fixed, non-reflective schema registry."""

    _schemas: dict[str, type[BaseModel]] = {
        "search_policy": SearchPolicyInput,
        "get_claim_status": GetClaimStatusInput,
        "submit_claim": SubmitClaimInput,
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._allowlist = ToolAllowlist(self._settings)

    def validate(self, tool_call: ProviderToolCall) -> BaseModel:
        """Parse JSON, enforce exact field policy, and return a typed input model."""

        try:
            self._allowlist.ensure_allowed(tool_call.name)
        except ToolAllowlistError as exc:
            raise ToolArgumentValidationError from exc

        schema = self._schemas.get(tool_call.name)
        if schema is None:
            raise ToolArgumentValidationError

        try:
            payload = json.loads(tool_call.arguments)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ToolArgumentValidationError from exc
        if not isinstance(payload, dict):
            raise ToolArgumentValidationError

        self._validate_json_types(tool_call.name, payload)
        try:
            return schema.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as exc:
            raise ToolArgumentValidationError from exc

    def normalize(self, tool_call: ProviderToolCall) -> str:
        """Return compact JSON from the validated typed model for CrewAI dispatch."""

        validated = self.validate(tool_call)
        return json.dumps(
            validated.model_dump(mode="json"),
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def _validate_json_types(tool_name: str, payload: dict[str, Any]) -> None:
        """Reject coercion-prone provider values before Pydantic business validation."""

        string_fields = {
            "search_policy": {"query"},
            "get_claim_status": {"claim_id"},
            "submit_claim": {"policy_number", "claim_type", "description"},
        }[tool_name]
        for field_name in string_fields:
            if field_name in payload and not isinstance(payload[field_name], str):
                raise ToolArgumentValidationError

        if tool_name == "submit_claim" and "amount" in payload:
            amount = payload["amount"]
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                raise ToolArgumentValidationError
            if not math.isfinite(float(amount)):
                raise ToolArgumentValidationError
