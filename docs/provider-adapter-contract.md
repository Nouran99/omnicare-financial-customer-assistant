# Provider Adapter Contract

US-021 introduces a replaceable language-model provider boundary. The application-facing `LLMProvider` protocol exposes a single `complete(messages, tools, response_schema)` operation. CrewAI tools, Flow orchestration, policy retrieval, claim services, and HTTP routes do not call the DeepSeek SDK directly.

## DeepSeek implementation

`DeepSeekProvider` uses the installed OpenAI SDK against the configurable DeepSeek OpenAI-compatible endpoint. It reads these values only from `Settings`:

| Environment variable | Purpose |
|---|---|
| `DEEPSEEK_API_KEY` | Authorized provider credential; required only at completion time and never committed. |
| `DEEPSEEK_BASE_URL` | OpenAI-compatible provider endpoint. |
| `DEEPSEEK_MODEL` | Verified enabled model name; no model is hard-coded in business logic. |
| `DEEPSEEK_TIMEOUT_SECONDS` | Provider request timeout; defaults to the confirmed value of `30` seconds. |

Adapter construction and module import do not create a network connection or make a provider request. The OpenAI-compatible client is built lazily only when `complete` is invoked with complete runtime configuration.

## Outputs and safety

The adapter converts SDK output into `ProviderCompletion`, which contains only textual content, normalized tool-call records, and an optional parsed Pydantic response model. It does not expose a raw SDK response or provider payload to application code.

Missing configuration, SDK failures, malformed completions, invalid tool-call shapes, and schema-parse failures become the existing safe `ProviderError`. Logs record only the provider name and exception type; prompts, messages, API keys, raw payloads, and provider diagnostics are excluded.

## Verification status

Default tests use injected fake clients and make no provider request. The current implementation has **not** performed a live DeepSeek smoke test because no authorized key and verified model name have been supplied for this task. If explicitly authorized later, the smoke test must read credentials only from an untracked local `.env` file and must not write them to output, tests, documentation, or Git.

The adapter is intentionally replaceable. An assessment-listed provider or local Ollama implementation can satisfy the same `LLMProvider` protocol without altering CrewAI tools, Flow logic, RAG services, or API contracts.
