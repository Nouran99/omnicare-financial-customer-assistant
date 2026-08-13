"""Tests for common provider-generated tool-call validation."""

from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.tools.submit_claim import SubmitClaimTool
from app.providers.deepseek import ProviderToolCall
from app.services.provider_tool_validator import (
    ProviderToolArgumentValidator,
    ToolArgumentValidationError,
)


def build_validator() -> ProviderToolArgumentValidator:
    return ProviderToolArgumentValidator(
        Settings(
            deepseek_model="deepseek-v4-flash",
            approved_tool_names="search_policy,get_claim_status,submit_claim",
        )
    )


def tool_call(name: str, arguments: str) -> ProviderToolCall:
    return ProviderToolCall(id="call-1", name=name, arguments=arguments)


def test_valid_json_is_schema_validated_and_normalized() -> None:
    validator = build_validator()

    normalized = validator.normalize(
        tool_call("search_policy", '{"query": "water damage coverage"}')
    )

    assert json.loads(normalized) == {"query": "water damage coverage"}


def test_malformed_json_is_rejected_before_dispatch() -> None:
    with pytest.raises(ToolArgumentValidationError) as error:
        build_validator().validate(tool_call("search_policy", '{"query":'))

    assert error.value.public_detail == "The assistant generated an invalid tool request."
    assert "query" not in str(error.value)


def test_missing_required_field_is_rejected() -> None:
    with pytest.raises(ToolArgumentValidationError):
        build_validator().validate(tool_call("get_claim_status", "{}"))


def test_unexpected_field_is_rejected_by_documented_extra_forbid_policy() -> None:
    with pytest.raises(ToolArgumentValidationError):
        build_validator().validate(
            tool_call(
                "submit_claim",
                '{"policy_number":"POL-1","claim_type":"Water Damage",'
                '"amount":12,"description":"Burst pipe","file_path":"/tmp/claims.json"}',
            )
        )


def test_wrong_string_type_is_rejected_without_dangerous_coercion() -> None:
    with pytest.raises(ToolArgumentValidationError):
        build_validator().validate(
            tool_call("get_claim_status", '{"claim_id": 8821}')
        )


def test_negative_amount_is_rejected_before_submission_persistence(tmp_path) -> None:
    claims_path = tmp_path / "claims.json"
    claims_path.write_text("[]\n", encoding="utf-8")
    before = claims_path.read_bytes()
    settings = Settings(
        deepseek_model="deepseek-v4-flash",
        claims_file_path=str(claims_path),
    )
    submit_claim = SubmitClaimTool(settings=settings)

    with pytest.raises(ToolArgumentValidationError):
        validated = build_validator().validate(
            tool_call(
                "submit_claim",
                '{"policy_number":"POL-1","claim_type":"Water Damage",'
                '"amount":-1,"description":"Burst pipe"}',
            )
        )
        submit_claim.run(**validated.model_dump())

    assert claims_path.read_bytes() == before


def test_unknown_tool_is_rejected_by_the_same_common_path() -> None:
    with pytest.raises(ToolArgumentValidationError):
        build_validator().validate(tool_call("run_shell", "{}"))
