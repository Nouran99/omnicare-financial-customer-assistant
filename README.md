# OmniCare Financial Customer Assistant

OmniCare is a production-minded prototype of an insurance customer assistant for three bounded journeys: answering policy-coverage questions from local policy evidence, looking up the status of a mock claim, and submitting a validated mock claim.

> **Prototype disclaimer:** This repository uses mock insurance data and is intended for technical-assessment demonstration. It is not a production insurance system and does not provide real coverage, authorization, or claims decisions.

## Project Status

The repository is being implemented incrementally from the approved OmniCare user-story backlog. The initial foundation stories establish the public repository layout, secret-protection rules, backend package, Next.js frontend scaffold, and Docker Compose service map before business behavior is added.

## Core Capabilities

| Capability | Planned implementation |
|---|---|
| Policy questions | FastAPI service with CrewAI orchestration and local policy retrieval. |
| Claim status | Read-only lookup against the supplied mock claims fixture. |
| Claim submission | Pydantic-validated atomic append to the mock claims fixture. |
| API foundation | Versioned FastAPI entry point, health check, strict chat models, safe errors, CORS, request IDs, and sanitized logs. |

## Repository Structure

```text
.
├── backend/    # FastAPI, CrewAI, retrieval, tools, and domain services
├── frontend/   # Next.js App Router web interface
├── data/       # Local policy and mock claims fixtures
├── docs/       # Architecture notes and walkthrough material
└── tests/      # Cross-cutting verification and acceptance tests
```

## Architecture

The target architecture is a lightweight Next.js frontend calling a versioned FastAPI backend. The backend will apply deterministic safety and validation controls around a single CrewAI support agent, local policy retrieval, and three bounded operational tools. The detailed diagram will be completed as the application services are implemented.

```text
Next.js frontend → FastAPI API → controlled CrewAI Flow → local policy retrieval / mock claims tools
```

## Quick Start

The initial service map is designed for the following reviewer workflow. The Compose services are intentionally placeholders until the application entry points and Dockerfiles are completed in subsequent stories.

```bash
cp .env.example .env
docker-compose up --build
```

| Service | Local port | Responsibility |
|---|---:|---|
| `frontend` | `3000` | Next.js App Router interface. |
| `backend` | `8000` | FastAPI, CrewAI, retrieval, and claims services. |

The Compose file references environment variables rather than embedding credentials. The backend and frontend service names are stable so later container-to-container requests can use `backend:8000` rather than an ambiguous `localhost` address.

## Local Development

Install and build the frontend with pnpm:

```bash
cd frontend
pnpm install
pnpm lint
pnpm build
pnpm dev
```

Create the backend environment and run its current scaffold checks with the project virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -e 'backend[test]'
.venv/bin/pytest -q
```

The backend package is imported from the repository root through the checked-in `pytest.ini`. Run the current FastAPI foundation with:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

The API contract, validation limits, safe error mapping, CORS behavior, request IDs, and structured logging are documented in [`docs/api-contract.md`](docs/api-contract.md). Claims validation, exact fixture contents, atomic persistence, description retention, and half-up amount rounding are documented in [`docs/claims-data-contract.md`](docs/claims-data-contract.md). Policy chunking, local Chroma indexing, threshold fallback, deterministic offline embeddings, and citation formatting are documented in [`docs/rag-contract.md`](docs/rag-contract.md).

## Configuration

Copy `.env.example` to `.env` for local development and provide authorized provider configuration only in the local environment. Never commit `.env`, API keys, or generated secrets. Runtime validation limits, claim status, decimal precision, data paths, CORS origin, log level, Chroma storage, retrieval thresholds, and related values are configuration-driven through the settings documented in `.env.example`. `DEEPSEEK_MODEL` remains a placeholder until the authorized provider configuration is verified in a later integration story.

## Development Scope

The implementation intentionally excludes authentication, production databases, cloud deployment, multi-agent delegation, provider-backed speech services, and any business rules not present in the assessment fixtures. Later changes must preserve the separation between deterministic application controls and model-assisted interpretation.
