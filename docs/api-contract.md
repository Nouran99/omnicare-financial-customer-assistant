# OmniCare API Foundation Contract

This document describes the FastAPI foundation delivered by US-006 through US-010. The endpoint remains intentionally independent of DeepSeek, retrieval, and claims data until later stories add the chat orchestration path.

## Application entry point

Run the backend from the repository root after installing the editable package:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

The application exposes OpenAPI documentation at `/docs` and `/openapi.json`.

## Health endpoint

```http
GET /api/v1/health
```

Successful response:

```json
{"status":"healthy"}
```

The health check does not read mock data, initialize a provider client, or require `DEEPSEEK_API_KEY`.

## Chat models

The public request contract is:

```json
{
  "user_id": "user-123",
  "message": "Is sudden pipe-burst water damage covered?"
}
```

`user_id` is a trimmed, non-empty string of at most 128 characters. `message` is a trimmed, non-empty string of at most 8,000 characters. Unexpected request fields are rejected.

The public response contract is:

```json
{
  "response": "The assistant response will be added by the support Flow in a later story.",
  "sources": [],
  "tool_calls": []
}
```

Tool-call summaries are bounded and expose only `name`, `status`, `arguments`, and `result_summary`. They do not expose API keys, hidden prompts, absolute paths, raw provider payloads, or the complete claims fixture.

## Errors

| Condition | Status | Public error code |
|---|---:|---|
| Request-body validation failure | 422 | `validation_error` |
| Provider failure | 502 | `provider_error` |
| Bounded tool failure | 500 | `tool_error` |
| Unexpected server failure | 500 | `internal_error` |

Error bodies are safe envelopes with `error`, `detail`, and the correlated `request_id`. Raw exception messages, stack traces, prompts, and provider payloads are not returned.

## CORS and request IDs

CORS permits only the configured `FRONTEND_ORIGIN`, which defaults to `http://localhost:3000`. Wildcard origins are not used.

Every response carries `X-Request-ID`. A valid UUID supplied in the same request header is propagated; otherwise the backend generates a UUID. The same ID is used in request lifecycle and failure logs.

## Logging

The backend emits one-line JSON logs to stdout at the configured `LOG_LEVEL`, defaulting to `INFO`. Request start/completion, request failure, tool invocation, provider failure, and handled application-error events are supported. Logs record identifiers, event names, status, duration, and safe type metadata only. Full messages, prompts, transcripts, claims records, API keys, tokens, and raw provider payloads are excluded.
