"""Versioned public API routes."""

from fastapi import APIRouter

from ..models.api import HealthResponse

api_router = APIRouter(prefix="/api/v1")


@api_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check process health",
    tags=["system"],
)
def health() -> HealthResponse:
    """Return deterministic process health without provider or data dependencies."""

    return HealthResponse()
