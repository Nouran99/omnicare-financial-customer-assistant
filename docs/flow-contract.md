# OmniCareSupportFlow Contract

`OmniCareSupportFlow.run(...)` is the single orchestration entry point for text and voice-transcript requests. It initializes typed `AssistantState`, evaluates the deterministic safety gate, stops immediately for blocked input, lazily constructs the bounded single-agent Crew for allowed input, kicks off the structured support task, merges sanitized tool observations, validates the `AssistantDraft`, and returns `ChatResponse`.

## State transitions

| Transition | Behavior |
|---|---|
| Initialize | Creates request/user/message state, generates a request ID when absent, and records `input_channel` as metadata. |
| Safety check | Runs before Crew construction or tool invocation. Blocked input returns the configured safe response with no sources or tool calls. |
| Crew execution | Allowed input reaches the configured one-agent sequential Crew. Provider and Crew failures become the configured safe provider response. |
| Observation merge | Converts trusted policy citations and tool event summaries into bounded `AssistantState` fields. Prior request observations are cleared before each run. |
| Draft validation | Enforces source requirements for coverage assertions, successful `submit_claim` evidence for claim-success text, blocked-draft tool exclusion, hidden-instruction rejection, and Pydantic field safety. |
| Finalization | Returns `ChatResponse` with `response`, `sources`, and sanitized `tool_calls` on every path. |

The default Flow builds the existing approved tools and task. Tests may inject a fake Crew, provider, or sanitized observation seam without making a network request. No raw provider payload, API key, filesystem path, full claims array, or hidden prompt enters the final response.
