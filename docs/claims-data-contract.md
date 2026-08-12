# Claims Data Contract

This document describes the claims domain delivered by US-011 through US-014. The implementation uses local mock JSON data behind typed models and repository boundaries; it does not provide production authorization or real insurance decisions.

## Stored records

The supplied `data/mock_claims.json` fixture contains exactly two records:

| Claim ID | Policy | Type | Status | Amount |
|---|---|---|---|---:|
| `CLM-8821` | `POL-1092` | Water Damage | Approved | 3500.00 |
| `CLM-9014` | `POL-3341` | Personal Property | Under Review | 1200.00 |

The original records intentionally have no user-ownership field and no description. Newly submitted records retain their validated `description` because that field is part of the submission contract. This does not create authentication or ownership enforcement.

## Validation

`ClaimSubmission` requires `policy_number`, `claim_type`, `amount`, and `description`. Text is trimmed and must be non-empty and within the configured limits. Claim type and policy number are not restricted by an undocumented enum or regular expression.

Amounts must be finite numeric values greater than the configured `CLAIM_AMOUNT_MIN`. They are rounded to the configured number of decimal places using financial half-up rounding. The default is two decimal places, so `42.125` becomes `42.13`. Amounts remain JSON numbers rather than formatted currency strings.

All operational limits and the initial claim status are loaded through `Settings`. They are represented in `.env.example` and passed through Compose. The default initial status is the confirmed value `Submitted`, but deployments can override it through `INITIAL_CLAIM_STATUS`.

## Submission confirmation IDs

The `submit_claim` tool generates the confirmation ID inside the trusted application layer. The default convention is `CLM-` followed by eight uppercase hexadecimal characters, for example `CLM-7A3F91C2`. The prefix, hex length, and maximum generation attempts are configuration-driven through `CLAIM_ID_PREFIX`, `CLAIM_ID_RANDOM_HEX_LENGTH`, and `CLAIM_ID_GENERATION_ATTEMPTS`. The tool checks generated IDs against the current repository before writing and never accepts a caller-supplied claim ID, status, path, or hidden control field.

## Repository boundaries

`ClaimsRepository` provides exact claim-ID lookup and typed not-found results. It never exposes the full claims array through an API route and does not mutate data during lookup.

`AtomicClaimsPersistence` accepts only a validated `StoredClaim`, reads the current fixture, serializes the updated array to a temporary file in the same directory, flushes it, and replaces the target with `os.replace`. A process-level lock protects concurrent writes within one process. The repository path is injected through configuration; callers cannot provide an arbitrary path to the append method.

## Controlled failure behavior

Missing files, invalid JSON, invalid record shapes, serialization failures, replacement failures, and duplicate claim IDs become controlled repository errors. Raw filesystem paths, JSON parser details, and tracebacks are not part of their public messages. The target file remains unchanged when replacement fails.
