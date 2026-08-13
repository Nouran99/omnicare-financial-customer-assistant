# GenAI Engineer Assessment Alignment

This matrix maps the attached `GenAIEngineerv1.0.pdf` requirements to the OmniCare implementation. It is intended to let a reviewer verify the submission without reconstructing the entire story history.

| Assessment requirement | Implementation evidence | Verification evidence |
|---|---|---|
| Working chat or voice web UI | `frontend/app/chat-client.tsx`, `frontend/lib/use-chat-state.ts`, `frontend/app/message-metadata.tsx`, and optional `frontend/app/voice-controls.tsx` | Frontend component and hook tests; production Next.js build; browser empty-state screenshot in `docs/screenshots/empty-ui.webp`. |
| `POST /api/v1/chat` contract | `backend/app/api/routes.py`, `backend/app/models/api.py`, `frontend/lib/api.ts`, and `frontend/app/api/v1/chat/route.ts` | `tests/test_chat_route.py`, `tests/test_endpoint_suite.py`, frontend API tests. |
| `GET /api/v1/health` contract | `backend/app/api/routes.py` and backend Docker `HEALTHCHECK` | Endpoint suite and Compose health status. |
| Supported agent framework | CrewAI one-agent sequential Crew inside the application-owned `OmniCareSupportFlow` | `backend/app/flows/crew.py`, `backend/app/flows/omnicare_support.py`, `tests/test_support_crew.py`, `tests/test_orchestration_integration.py`. |
| Policy RAG with citations | `PolicyDocumentLoader`, `ChromaPolicyVectorStore`, `PolicyRetriever`, `CitationFormatter`, deterministic coverage preflight, and `data/sample_policy.md` | `tests/test_policy_rag.py`, `tests/test_policy_api_scenario.py`, endpoint/orchestration suites, and repeated live container policy requests. |
| `get_claim_status(claim_id)` | `backend/app/tools/get_claim_status.py`, `ClaimsRepository`, and `data/mock_claims.json` | `tests/test_get_claim_status_tool.py`, `tests/test_claim_api_scenario.py`, endpoint/orchestration suites. |
| `submit_claim(...)` | `backend/app/tools/submit_claim.py`, typed schemas, atomic persistence, configured rounding/status/ID behavior | `tests/test_submit_claim_tool.py`, `tests/test_claim_submission_api_scenario.py`, endpoint/orchestration/security suites. |
| Safety and validation | `DeterministicSafetyGate`, provider argument validator, fixed tool allowlist, draft grounding validator, safe error mapping, and summary sanitizer | `tests/test_safety_gate.py`, `tests/test_provider_tool_validator.py`, `tests/test_tool_allowlist.py`, `tests/test_tool_summary_sanitizer.py`, `tests/test_security_regression.py`. |
| Clean `/frontend` and `/backend` separation | Repository directories, `backend/pyproject.toml`, `frontend/package.json`, separate Dockerfiles | Docker configuration tests, backend regression, frontend typecheck/lint/build. |
| Docker setup | `backend/Dockerfile`, `frontend/Dockerfile`, root `docker-compose.yml`, `.dockerignore` | Both images built successfully; backend health-gated Compose startup; Docker configuration tests. |
| Reviewer README | Root `README.md` with feature matrix, architecture diagram, two-minute run, API examples, framework rationale, RAG/tool/security/voice/limitation notes | README link/file audit and clean Compose configuration validation. |
| Walkthrough evidence | `docs/walkthrough.md` with empty UI screenshot plus reproducible policy, claim-status, claim-submission, refusal, unsupported-coverage, and test instructions | Screenshot review, endpoint/orchestration/security tests, frontend/browser checks. |
| Automated tests | Backend pytest suite and frontend Vitest suite | Full suites, typecheck, lint, and production build. |
| Local/no-paid-cloud constraint | Local Chroma with deterministic hash embeddings; provider is an external configurable DeepSeek-compatible API; no cloud vector store or paid service is required by the repository | `backend/app/services/policy_store.py`, `.env.example`, offline test suite. |

## Explicit fixture alignment

The repository’s `data/sample_policy.md` contains sudden pipe-burst coverage up to `$25,000` with a `$500` deductible, gradual leaks and floods excluded, and personal-property protection up to `$10,000` with appraisal receipts required above `$2,500`.

The repository’s `data/mock_claims.json` contains `CLM-8821` / `POL-1092` / `Water Damage` / `Approved` / `3500.00` and `CLM-9014` / `POL-3341` / `Personal Property` / `Under Review` / `1200.00`.

## Final audit policy

The public repository must not contain `.env`, provider keys, private employer material, generated Chroma runtime state, or raw provider payloads. Before the final commit, the delivery process runs `git diff --check`, a tracked-secret pattern scan, the backend and frontend suites, frontend typecheck/lint/build, Docker Compose configuration validation, image builds, and a clean status check.
