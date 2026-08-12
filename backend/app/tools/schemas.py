"""Typed CrewAI-compatible schemas for OmniCare business tools."""

from __future__ import annotations

from abc import ABC
from typing import Annotated, Literal

from crewai.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.config import get_settings
from ..models.claims import StoredClaim

ToolExecutionStatus = Literal["success", "not_found", "failure"]


def _bounded_text(value: str, *, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} exceeds the configured length")
    return normalized


class SearchPolicyInput(BaseModel):
    """Input for the read-only policy retrieval tool."""

    model_config = ConfigDict(extra="forbid")

    query: str

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return _bounded_text(
            value,
            field_name="query",
            max_length=get_settings().policy_query_max_length,
        )


class PolicyEvidenceOutput(BaseModel):
    """Safe policy evidence returned to model context."""

    model_config = ConfigDict(extra="forbid")

    section_title: str
    text: str
    citation: str

    @field_validator("section_title")
    @classmethod
    def validate_section_title(cls, value: str) -> str:
        return _bounded_text(
            value,
            field_name="section_title",
            max_length=get_settings().policy_section_title_max_length,
        )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _bounded_text(
            value,
            field_name="text",
            max_length=get_settings().policy_chunk_text_max_length,
        )

    @field_validator("citation")
    @classmethod
    def validate_citation(cls, value: str) -> str:
        return _bounded_text(
            value,
            field_name="citation",
            max_length=get_settings().policy_citation_max_length,
        )


class SearchPolicySuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    results: list[PolicyEvidenceOutput] = Field(..., min_length=1)


class SearchPolicyNotFound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_found"] = "not_found"
    message: str
    results: list[PolicyEvidenceOutput] = Field(default_factory=list)


class SearchPolicyFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["failure"] = "failure"
    message: str
    results: list[PolicyEvidenceOutput] = Field(default_factory=list)


SearchPolicyResult = Annotated[
    SearchPolicySuccess | SearchPolicyNotFound | SearchPolicyFailure,
    Field(discriminator="status"),
]


class SearchPolicyOutput(BaseModel):
    """Concrete CrewAI result schema covering all policy-search states."""

    model_config = ConfigDict(extra="forbid")

    status: ToolExecutionStatus
    results: list[PolicyEvidenceOutput] = Field(default_factory=list)
    message: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "SearchPolicyOutput":
        if self.status == "success" and not self.results:
            raise ValueError("successful policy search requires results")
        if self.status != "success" and self.results:
            raise ValueError("non-success policy search cannot include results")
        if self.status != "success" and not self.message:
            raise ValueError("non-success policy search requires a message")
        return self


class GetClaimStatusInput(BaseModel):
    """Input for exact claim-ID lookup without path access."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        return _bounded_text(
            value,
            field_name="claim_id",
            max_length=get_settings().claim_id_max_length,
        )


class ClaimSummaryOutput(BaseModel):
    """Safe claim fields suitable for model context."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    policy_number: str
    claim_type: str
    status: str
    amount: float

    @classmethod
    def from_claim(cls, claim: StoredClaim) -> "ClaimSummaryOutput":
        return cls(
            claim_id=claim.claim_id,
            policy_number=claim.policy_number,
            claim_type=claim.claim_type,
            status=claim.status,
            amount=claim.amount,
        )


class GetClaimStatusSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    claim: ClaimSummaryOutput


class GetClaimStatusNotFound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_found"] = "not_found"
    claim_id: str
    message: str


class GetClaimStatusFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["failure"] = "failure"
    message: str


GetClaimStatusResult = Annotated[
    GetClaimStatusSuccess | GetClaimStatusNotFound | GetClaimStatusFailure,
    Field(discriminator="status"),
]


class GetClaimStatusOutput(BaseModel):
    """Concrete CrewAI result schema covering all claim lookup states."""

    model_config = ConfigDict(extra="forbid")

    status: ToolExecutionStatus
    claim: ClaimSummaryOutput | None = None
    claim_id: str | None = None
    message: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "GetClaimStatusOutput":
        if self.status == "success" and self.claim is None:
            raise ValueError("successful claim lookup requires a claim")
        if self.status == "not_found" and (not self.claim_id or not self.message):
            raise ValueError("claim not-found output requires claim_id and message")
        if self.status == "failure" and not self.message:
            raise ValueError("claim failure output requires a message")
        if self.status != "success" and self.claim is not None:
            raise ValueError("non-success claim lookup cannot include a claim")
        return self


class SubmitClaimInput(BaseModel):
    """Validated claim-submission input without filesystem controls."""

    model_config = ConfigDict(extra="forbid")

    policy_number: str
    claim_type: str
    amount: float
    description: str

    @field_validator("policy_number")
    @classmethod
    def validate_policy_number(cls, value: str) -> str:
        return _bounded_text(
            value,
            field_name="policy_number",
            max_length=get_settings().policy_number_max_length,
        )

    @field_validator("claim_type")
    @classmethod
    def validate_claim_type(cls, value: str) -> str:
        return _bounded_text(
            value,
            field_name="claim_type",
            max_length=get_settings().claim_type_max_length,
        )

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _bounded_text(
            value,
            field_name="description",
            max_length=get_settings().claim_description_max_length,
        )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        if value <= get_settings().claim_amount_min:
            raise ValueError("amount must be greater than the configured minimum")
        return value


class SubmitClaimSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    claim_id: str
    claim_status: str
    message: str


class SubmitClaimFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["failure"] = "failure"
    message: str


SubmitClaimResult = Annotated[
    SubmitClaimSuccess | SubmitClaimFailure,
    Field(discriminator="status"),
]


class SubmitClaimOutput(BaseModel):
    """Concrete CrewAI result schema covering claim submission states."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failure"]
    claim_id: str | None = None
    claim_status: str | None = None
    message: str

    @model_validator(mode="after")
    def validate_state(self) -> "SubmitClaimOutput":
        if self.status == "success" and (not self.claim_id or not self.claim_status):
            raise ValueError("successful claim submission requires claim_id and claim_status")
        if self.status == "failure" and (self.claim_id or self.claim_status):
            raise ValueError("failed claim submission cannot include claim details")
        return self


class _SchemaDefinitionTool(BaseTool, ABC):
    """CrewAI-compatible schema carrier; execution is added per tool story."""

    def _run(self, **kwargs: object) -> object:
        raise NotImplementedError("US-022 defines schemas; execution is added by tool stories")


class SearchPolicyToolDefinition(_SchemaDefinitionTool):
    name: str = "search_policy"
    description: str = (
        "Search the supplied local policy for relevant coverage evidence and citations. "
        "Returns structured evidence or a safe no-results outcome."
    )
    args_schema: type[BaseModel] = SearchPolicyInput
    result_schema: type[BaseModel] = SearchPolicyOutput


class GetClaimStatusToolDefinition(_SchemaDefinitionTool):
    name: str = "get_claim_status"
    description: str = (
        "Look up one claim by its exact claim ID and return a safe structured status."
    )
    args_schema: type[BaseModel] = GetClaimStatusInput
    result_schema: type[BaseModel] = GetClaimStatusOutput


class SubmitClaimToolDefinition(_SchemaDefinitionTool):
    name: str = "submit_claim"
    description: str = (
        "Validate and submit a claim using the configured claims service. "
        "Never accepts filesystem paths or arbitrary dictionaries."
    )
    args_schema: type[BaseModel] = SubmitClaimInput
    result_schema: type[BaseModel] = SubmitClaimOutput
