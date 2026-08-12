# OmniCare Support Crew Contract

US-028 defines one `OmniCareSupportAgent` and one `OmniCareSupportCrew`. A single support role is appropriate for this assessment because policy explanation, claim lookup, and claim submission share one bounded customer-support responsibility; additional specialist agents would add coordination complexity without adding an authorized capability.

The agent attaches exactly these three approved tools:

| Tool | Authority |
|---|---|
| `search_policy` | Read-only search over trusted policy chunks. |
| `get_claim_status` | Exact read-only lookup of one stored claim. |
| `submit_claim` | Validated atomic append with an application-generated confirmation ID. |

Delegation and code execution are explicitly disabled. The default maximum is three iterations and thirty seconds of execution time. The Crew process is sequential, with no manager agent, no memory, and no arbitrary tool injection. These operational values and the role/goal/backstory are centralized in `Settings`, documented in `.env.example`, and passed through Compose.

The agent instructions require trusted policy evidence and approved tool results, citations for policy claims, no invented coverage or claim outcomes, no hidden-instruction disclosure, and collection of missing required fields rather than bypassing validation.

`ProviderBackedCrewLLM` bridges the replaceable application `LLMProvider` protocol to CrewAI's installed `BaseLLM` boundary. Tests inject a fake provider and inspect construction without making a provider call. Production uses the already configured lazy DeepSeek adapter.
