# AssistantState Contract

US-027 defines the typed state shared by the future `OmniCareSupportFlow`. Text requests and voice transcripts use the same business field, `message`; `input_channel` is metadata with allowed values `text` and `voice`.

| Field | Type | Initial value |
|---|---|---|
| `request_id` | Bounded string | Caller-provided ID or generated UUID. |
| `user_id` | Bounded string | Required caller identity value. |
| `message` | Bounded string | Required text or voice transcript. |
| `input_channel` | `text` or `voice` | `text`. |
| `safety_result` | Optional `SafetyCheckResult` | `None`. |
| `intent` | Optional bounded string | `None`. |
| `retrieved_context` | List of typed policy evidence | Empty list. |
| `tool_events` | List of bounded `ToolCallSummary` records | Empty list. |
| `draft_response` and `final_response` | Optional bounded strings | `None`. |
| `sources` | Deduplicated bounded strings | Empty list. |
| `error_code` | Optional bounded string | `None`. |

`append_tool_event` preserves existing records and enforces the configured event limit. `append_source` deduplicates and enforces the configured source limit. Pydantic serialization exposes only these typed fields; it does not include API keys, provider settings, full claims arrays, filesystem paths, hidden prompts, or raw provider payloads.
