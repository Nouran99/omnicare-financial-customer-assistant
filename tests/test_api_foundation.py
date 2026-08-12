"""Acceptance tests for the FastAPI foundation stories."""

from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import ProviderError, ToolError
from app.core.logging import (
    JsonLogFormatter,
    log_event,
    log_provider_failure,
    log_tool_event,
)
from app.core.middleware import REQUEST_ID_HEADER
from app.main import create_app
from app.models.api import ChatRequest, ChatResponse, ToolCallSummary



def make_client() -> TestClient:
    application = create_app(
        Settings(frontend_origin="http://localhost:3000", log_level="WARNING")
    )
    return TestClient(application)


def test_application_imports_without_provider_configuration() -> None:
    client = make_client()

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "OmniCare Financial Customer Assistant"


def test_health_is_deterministic_and_provider_independent() -> None:
    client = make_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert response.headers[REQUEST_ID_HEADER]


def test_chat_request_rejects_blank_oversized_and_extra_fields() -> None:
    valid = ChatRequest(user_id="user-123", message="Is water damage covered?")
    assert valid.user_id == "user-123"
    settings = get_settings()

    for payload in (
        {"user_id": " ", "message": "hello"},
        {"user_id": "user", "message": " "},
        {"user_id": "x" * (settings.user_id_max_length + 1), "message": "hello"},
        {"user_id": "user", "message": "x" * (settings.message_max_length + 1)},
        {"user_id": "user", "message": "hello", "unexpected": True},
    ):
        try:
            ChatRequest.model_validate(payload)
        except ValidationError:
            continue
        raise AssertionError(f"payload should be rejected: {payload}")


def test_chat_response_has_stable_safe_shape() -> None:
    response = ChatResponse(
        response="The policy answer is grounded in the supplied document.",
        sources=["sample_policy.md — Section 1: Home Water Damage Coverage"],
        tool_calls=[
            ToolCallSummary(
                name="search_policy",
                status="success",
                arguments="query=water damage",
                result_summary="Section 1 retrieved",
            )
        ],
    )

    serialized = response.model_dump()

    assert set(serialized) == {"response", "sources", "tool_calls"}
    assert "api_key" not in json.dumps(serialized)
    assert "claims_database" not in json.dumps(serialized)


def test_configured_origin_is_allowed_and_other_origins_are_not() -> None:
    client = make_client()

    allowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    blocked = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert blocked.headers.get("access-control-allow-origin") is None


def test_validation_errors_use_safe_422_contract() -> None:
    application = create_app(Settings(frontend_origin="http://localhost:3000"))
    router = APIRouter()

    @router.post("/test/validated")
    def validated(request: ChatRequest) -> ChatRequest:
        return request

    application.include_router(router)
    client = TestClient(application)

    response = client.post("/test/validated", json={"user_id": "", "message": ""})

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"
    assert "traceback" not in response.text.lower()
    assert response.headers[REQUEST_ID_HEADER]


def test_provider_and_tool_errors_are_mapped_without_raw_details() -> None:
    application = create_app(Settings(frontend_origin="http://localhost:3000"))
    router = APIRouter()

    @router.get("/test/provider")
    def provider_failure() -> None:
        raise ProviderError("raw provider payload should not escape")

    @router.get("/test/tool")
    def tool_failure() -> None:
        raise ToolError("raw tool details should not escape")

    application.include_router(router)
    client = TestClient(application, raise_server_exceptions=False)

    provider_response = client.get("/test/provider")
    tool_response = client.get("/test/tool")

    assert provider_response.status_code == 502
    assert provider_response.json()["error"] == "provider_error"
    assert "raw provider payload" not in provider_response.text
    assert tool_response.status_code == 500
    assert tool_response.json()["error"] == "tool_error"
    assert "raw tool details" not in tool_response.text


def test_unexpected_errors_are_generic_and_do_not_expose_tracebacks() -> None:
    application = create_app(Settings(frontend_origin="http://localhost:3000"))
    router = APIRouter()

    @router.get("/test/unexpected")
    def unexpected_failure() -> None:
        raise RuntimeError("secret implementation detail")

    application.include_router(router)
    client = TestClient(application, raise_server_exceptions=False)

    response = client.get("/test/unexpected")

    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert "secret implementation detail" not in response.text
    assert "traceback" not in response.text.lower()


def test_request_id_is_propagated_or_generated() -> None:
    client = make_client()
    supplied_id = str(uuid4())

    supplied = client.get(
        "/api/v1/health", headers={REQUEST_ID_HEADER: supplied_id}
    )
    generated = client.get("/api/v1/health")

    assert supplied.headers[REQUEST_ID_HEADER] == supplied_id
    UUID(generated.headers[REQUEST_ID_HEADER])
    assert generated.headers[REQUEST_ID_HEADER] != supplied_id


def test_tool_and_provider_events_are_traceable_without_payloads(caplog) -> None:
    logger = logging.getLogger("omnicare.test.events")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_tool_event(
            logger,
            request_id="request-456",
            tool_name="submit_claim",
            status="success",
        )
        log_provider_failure(
            logger,
            request_id="request-456",
            provider="deepseek",
            error_type="TimeoutError",
        )

    assert [record.event for record in caplog.records] == [
        "tool_invoked",
        "provider_failure",
    ]
    assert caplog.records[0].fields == {
        "tool_name": "submit_claim",
        "status": "success",
    }
    assert caplog.records[1].fields == {
        "provider": "deepseek",
        "error_type": "TimeoutError",
    }


def test_json_logging_excludes_sensitive_fields(caplog) -> None:
    logger = logging.getLogger("omnicare.test.logging")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(
            logger,
            event="tool_invoked",
            request_id="request-123",
            tool_name="get_claim_status",
            status="success",
            message="do not log this prompt",
            api_key="do not log this key",
            claims="do not log this record",
        )

    record = caplog.records[-1]
    assert record.event == "tool_invoked"
    assert record.request_id == "request-123"
    assert record.fields == {
        "tool_name": "get_claim_status",
        "status": "success",
    }

    formatted = JsonLogFormatter().format(record)
    assert json.loads(formatted) == {
        "event": "tool_invoked",
        "level": "INFO",
        "request_id": "request-123",
        "status": "success",
        "tool_name": "get_claim_status",
    }
