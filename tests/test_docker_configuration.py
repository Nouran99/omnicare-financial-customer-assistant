"""US-049 static Docker and Compose configuration checks."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_backend_dockerfile_installs_project_and_exposes_health_check() -> None:
    dockerfile = read("backend/Dockerfile")

    assert "FROM python:3.12-slim" in dockerfile
    assert "COPY backend/pyproject.toml /workspace/backend/pyproject.toml" in dockerfile
    assert "COPY backend/app /workspace/backend/app" in dockerfile
    assert "COPY data /workspace/data" in dockerfile
    assert "python -m pip install --no-cache-dir /workspace/backend" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/api/v1/health" in dockerfile
    assert '"uvicorn", "app.main:app"' in dockerfile


def test_frontend_dockerfile_uses_frozen_lockfile_and_production_start() -> None:
    dockerfile = read("frontend/Dockerfile")

    assert "FROM node:22-alpine" in dockerfile
    assert "COPY frontend/package.json frontend/pnpm-lock.yaml ./" in dockerfile
    assert "pnpm install --frozen-lockfile" in dockerfile
    assert "RUN pnpm build" in dockerfile
    assert '"pnpm", "start", "--hostname", "0.0.0.0"' in dockerfile


def test_compose_builds_services_and_gates_frontend_on_backend_health() -> None:
    compose = read("docker-compose.yml")

    assert "dockerfile: backend/Dockerfile" in compose
    assert "dockerfile: frontend/Dockerfile" in compose
    assert "working_dir: /workspace" in compose
    assert "condition: service_healthy" in compose
    assert '"uvicorn", "app.main:app"' in compose
    assert '"pnpm", "start", "--hostname", "0.0.0.0"' in compose
    assert "./data:/workspace/data" in compose
    assert "backend_runtime:/workspace/runtime" in compose
    assert "CREW_TASK_POLICY_EVIDENCE_CONTEXT_TEMPLATE" in compose
    assert "POLICY_QUERY_INTENT_PATTERNS" in compose
    assert "POLICY_QUERY_EXCLUSION_PATTERNS" in compose


def test_frontend_compose_environment_contains_only_server_side_backend_origin() -> None:
    compose = read("docker-compose.yml")
    frontend_section = compose.split("  frontend:\n", maxsplit=1)[1]

    assert "BACKEND_ORIGIN: http://backend:8000" in frontend_section
    assert "DEEPSEEK_API_KEY" not in frontend_section
    assert "DEEPSEEK_BASE_URL" not in frontend_section


def test_dockerignore_excludes_local_secrets_and_generated_runtime() -> None:
    dockerignore = read(".dockerignore")

    assert ".env" in dockerignore
    assert ".venv" in dockerignore
    assert ".git" in dockerignore
    assert "runtime" in dockerignore
    assert "chroma" in dockerignore
