# Deterministic Safety-Gate Contract

US-026 adds a small deterministic gate before any LLM, CrewAI tool, retrieval, or claim operation. It normalizes case and whitespace, checks a configured set of narrow phrase groups, and returns a typed `SafetyCheckResult`.

## Result model

| Field | Meaning |
|---|---|
| `allowed` | Whether the request may proceed to the next application layer. |
| `reason_code` | One of `allowed`, `prompt_injection`, `hidden_data_access`, `tool_bypass`, `administrator_impersonation`, or `required_field_bypass`. |
| `reason` | A safe configured message that never includes the matched input. |

The gate's `run(message, action)` method returns the safety result and invokes `action` only when the result is allowed. A blocked result returns no action value, which makes the no-tool/no-mutation guarantee directly testable.

## Configuration

Pattern groups and safe messages are centralized in `Settings` and documented in `.env.example`. The defaults cover explicit requests to ignore or reveal system instructions, access hidden claims or environment data, bypass tool validation, impersonate an administrator, or bypass required submission fields. Pattern priority is configurable and unknown group names are ignored safely.

## Prototype limitation

This is a narrow deterministic prototype control, not a complete prompt-injection defense. It does not understand every indirect, encoded, multilingual, or novel attack. Later layers must still enforce typed schemas, service boundaries, authorization controls, safe errors, and deterministic write rules. The gate is intentionally outside the LLM and must run before agent creation and tool execution.
