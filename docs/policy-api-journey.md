# Policy API Journey

US-032 verifies the policy question path through `POST /api/v1/chat` using a fake Crew/provider and fake retrieval seam in deterministic tests. The policy question is:

```json
{
  "user_id": "policyholder-1",
  "message": "Is sudden pipe-burst damage covered?"
}
```

The expected successful response shape is:

```json
{
  "response": "Sudden pipe-burst damage is covered up to $25,000 with a $500 deductible. Gradual leaks and floods are excluded.",
  "sources": [
    "sample_policy.md — Section 1: Home Water Damage Coverage"
  ],
  "tool_calls": [
    {
      "name": "search_policy",
      "status": "success",
      "arguments": null,
      "result_summary": "Policy evidence returned."
    }
  ]
}
```

The test asserts the required `$25,000` limit, `$500` deductible, gradual-leak and flood exclusions, the Section 1 citation, and the absence of claim-tool calls. An unsupported earthquake question returns a safe no-evidence response with no invented coverage or policy sources.

The CrewAI provider bridge now exposes native provider tool calls to CrewAI’s native execution loop. The task instructions require `search_policy` before drafting coverage answers, `get_claim_status` for status questions, and `submit_claim` only after required fields are present. The offline acceptance suite remains the deterministic gate; one authorized live policy smoke request was attempted using the local credential and returned HTTP 200 with the configured safe fallback before the native tool-call bridge correction. No credential or raw provider response is stored in the repository.
