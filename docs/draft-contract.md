# AssistantDraft Contract

US-029 keeps the Crew output smaller than internal `AssistantState`. It contains the fields needed for the public response and deterministic validation decisions: `response`, `sources`, `tool_calls`, `safety_result`, optional `follow_up_question`, and optional `error_code`.

The CrewAI task uses Pydantic `output_pydantic=AssistantDraft` and a callable deterministic guardrail. The guardrail accepts only the installed CrewAI `TaskOutput` boundary or typed equivalent, parses the draft into Pydantic, and returns either a validated `AssistantDraft` or a bounded failure code. It never returns raw provider output, hidden prompts, filesystem paths, or exception text.

The guardrail enforces four rules. A response containing a configured coverage assertion must include at least one trusted source. A response containing a configured claim-success phrase must include a successful `submit_claim` tool event. A blocked safety result may not contain tool calls. A response that matches configured hidden-instruction patterns is rejected. Malformed or extra fields are rejected by Pydantic and become the safe `malformed_draft` validation code.

Coverage and claim-success phrase groups are operational configuration in `Settings`, `.env.example`, and Compose. The current defaults are intentionally narrow and can be extended without changing validator code. Validated drafts map directly to `ChatResponse` through `to_chat_response()`.
