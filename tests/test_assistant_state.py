"""Tests for the typed US-027 AssistantState contract."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.flows.state import AssistantState, initialize_assistant_state
from app.models.api import ChatRequest, ToolCallSummary
from app.models.safety import SafetyCheckResult


def test_new_text_request_creates_valid_initial_state_with_uuid_fallback() -> None:
    state = initialize_assistant_state(
        user_id="user-1",
        message="What does my policy cover?",
    )

    UUID(state.request_id)
    assert state.user_id == "user-1"
    assert state.message == "What does my policy cover?"
    assert state.input_channel == "text"
    assert state.safety_result is None
    assert state.intent is None
    assert state.retrieved_context == []
    assert state.tool_events == []
    assert state.draft_response is None
    assert state.final_response is None
    assert state.sources == []
    assert state.error_code is None


def test_voice_transcript_uses_same_message_field_and_explicit_request_id() -> None:
    state = initialize_assistant_state(
        user_id="user-2",
        message="What is the status of my claim?",
        request_id="req-voice-1",
        input_channel="voice",
    )

    assert state.request_id == "req-voice-1"
    assert state.input_channel == "voice"
    assert state.message == "What is the status of my claim?"

    from_request = AssistantState.from_chat_request(
        ChatRequest(user_id="user-2", message="Transcript"),
        request_id="req-voice-2",
        input_channel="voice",
    )
    assert from_request.message == "Transcript"
    assert from_request.input_channel == "voice"


def test_tool_events_append_without_replacing_prior_events() -> None:
    state = initialize_assistant_state(user_id="user-1", message="Check my claim")
    first = ToolCallSummary(name="get_claim_status", status="success")
    second = ToolCallSummary(name="search_policy", status="success")

    state.append_tool_event(first).append_tool_event(second)

    assert [event.name for event in state.tool_events] == [
        "get_claim_status",
        "search_policy",
    ]


def test_state_serialization_contains_only_typed_safe_fields() -> None:
    state = initialize_assistant_state(user_id="user-1", message="Policy question")
    state.safety_result = SafetyCheckResult.allowed_result("Allowed")
    state.append_source("sample_policy.md — Section 1: Home Water Damage Coverage")
    state.append_tool_event(ToolCallSummary(name="search_policy", status="success"))
    state.final_response = "The policy covers sudden pipe bursts."

    serialized = json.loads(state.model_dump_json())

    assert set(serialized) == {
        "request_id",
        "user_id",
        "message",
        "input_channel",
        "safety_result",
        "intent",
        "retrieved_context",
        "tool_events",
        "draft_response",
        "final_response",
        "sources",
        "error_code",
    }
    serialized_text = json.dumps(serialized).lower()
    assert "api_key" not in serialized_text
    assert "deepseek" not in serialized_text
    assert "system prompt" not in serialized_text
    assert "claims_file_path" not in serialized_text
    assert "mock_claims.json" not in serialized_text


def test_state_rejects_invalid_channel_extra_fields_and_blank_required_values() -> None:
    with pytest.raises(ValidationError):
        initialize_assistant_state(
            user_id="user-1",
            message="Question",
            input_channel="phone",  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        AssistantState(
            request_id="req-1",
            user_id="user-1",
            message="Question",
            unexpected="value",
        )
    with pytest.raises(ValidationError):
        initialize_assistant_state(user_id=" ", message="Question")
