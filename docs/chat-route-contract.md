# Chat Route Contract

US-031 exposes `POST /api/v1/chat` as a thin FastAPI boundary over `OmniCareSupportFlow`. The route validates the existing `ChatRequest` model, forwards `user_id`, `message`, and the middleware request ID to the Flow, and returns the Flow's `ChatResponse`. It contains no provider prompts, retrieval logic, claims-file logic, or tool orchestration.

A valid request returns HTTP 200 with `response`, `sources`, and `tool_calls`. Blocked requests and failures normalized inside the Flow also return HTTP 200 with safe response text and empty collections where appropriate. Invalid request bodies use the existing safe HTTP 422 `ErrorResponse`; provider or domain exceptions that escape the Flow use the existing safe application error mapping, including HTTP 502 for `ProviderError`.

The route preserves a bounded printable incoming `X-Request-ID` or generates a UUID when none is supplied. The same value is passed to the Flow and returned in the response header. Tests override `get_support_flow` with a fake Flow, so route verification never requires a live provider.

The exact curl request used for local verification is:

```bash
curl -i -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: us031-curl-test' \
  --data '{"user_id":"user-1","message":"What does my policy cover?"}'
```
