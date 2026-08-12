"""Typed claim models shared by repositories, tools, and API layers."""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.config import get_settings


def _trimmed(value: str, *, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized


def _round_amount(value: float) -> float:
    """Round numeric money using configured decimal places and financial half-up rules."""

    settings = get_settings()
    quantum = Decimal("1").scaleb(-settings.claim_amount_decimal_places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


class ClaimBase(BaseModel):
    """Fields common to stored claims and newly submitted claims."""

    model_config = ConfigDict(extra="forbid")

    policy_number: str = Field(...)
    claim_type: str = Field(...)
    amount: float = Field(..., allow_inf_nan=False)

    @field_validator("policy_number")
    @classmethod
    def validate_policy_number(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="policy_number",
            max_length=get_settings().policy_number_max_length,
        )

    @field_validator("claim_type")
    @classmethod
    def validate_claim_type(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="claim_type",
            max_length=get_settings().claim_type_max_length,
        )

    @field_validator("amount", mode="before")
    @classmethod
    def reject_non_numeric_amount(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("amount must be a finite numeric value")
        if not math.isfinite(float(value)):
            raise ValueError("amount must be finite")
        return value

    @field_validator("amount")
    @classmethod
    def normalize_amount(cls, value: float) -> float:
        settings = get_settings()
        if not math.isfinite(value) or value <= settings.claim_amount_min:
            raise ValueError(
                f"amount must be finite and greater than {settings.claim_amount_min}"
            )
        return _round_amount(value)


class StoredClaim(ClaimBase):
    """Persisted claim record.

    The original fixture records omit ``description``. Newly submitted records retain
    the validated description, so the field is optional for backward-compatible
    fixture validation and populated for new claims.
    """

    claim_id: str = Field(...)
    status: str = Field(...)
    description: str | None = Field(default=None)

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="claim_id",
            max_length=get_settings().claim_id_max_length,
        )

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="status",
            max_length=get_settings().claim_status_max_length,
        )

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _trimmed(
            value,
            field_name="description",
            max_length=get_settings().claim_description_max_length,
        )


class ClaimSubmission(ClaimBase):
    """Validated input required to submit a new claim."""

    description: str = Field(...)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="description",
            max_length=get_settings().claim_description_max_length,
        )


class ClaimStatusLookupRequest(BaseModel):
    """Exact claim-ID lookup input."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(...)

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="claim_id",
            max_length=get_settings().claim_id_max_length,
        )


class ClaimStatusFound(BaseModel):
    """Successful claim lookup result."""

    model_config = ConfigDict(extra="forbid")

    found: Literal[True] = True
    claim: StoredClaim


class ClaimStatusNotFound(BaseModel):
    """Safe unknown-claim result."""

    model_config = ConfigDict(extra="forbid")

    found: Literal[False] = False
    claim_id: str
    reason: Literal["not_found"] = "not_found"


ClaimStatusResult = Annotated[
    ClaimStatusFound | ClaimStatusNotFound,
    Field(discriminator="found"),
]


class ClaimPersistenceResult(BaseModel):
    """Typed result returned after an atomic claim replacement succeeds."""

    model_config = ConfigDict(extra="forbid")

    success: Literal[True] = True
    claim: StoredClaim


class ClaimToolEvent(BaseModel):
    """Safe internal event model for later tool-call summaries."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(...)
    status: str = Field(...)
    arguments: dict[str, str] | None = Field(default=None)
    claim_id: str | None = Field(default=None)
    claim_status: str | None = Field(default=None)
    confirmation_id: str | None = Field(default=None)
    request_id: str | None = Field(default=None)
    result_summary: str | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="name",
            max_length=get_settings().tool_name_max_length,
        )

    @field_validator("status")
    @classmethod
    def validate_status_text(cls, value: str) -> str:
        return _trimmed(
            value,
            field_name="status",
            max_length=get_settings().tool_status_max_length,
        )

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _trimmed(
            value,
            field_name="request_id",
            max_length=get_settings().request_id_max_length,
        )

    @field_validator("result_summary")
    @classmethod
    def validate_result_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _trimmed(
            value,
            field_name="result_summary",
            max_length=get_settings().tool_result_max_length,
        )
