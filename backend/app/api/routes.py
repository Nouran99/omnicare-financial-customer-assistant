"""Versioned public API routes."""

from fastapi import APIRouter, Depends, Request

from ..flows.omnicare_support import OmniCareSupportFlow
from ..models.api import ChatRequest, ChatResponse, HealthResponse

api_router = APIRouter(prefix="/api/v1")


def get_support_flow() -> OmniCareSupportFlow:
    """Create the application Flow at request time for clean dependency overrides."""

    return OmniCareSupportFlow()


@api_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check process health",
    tags=["system"],
)
def health() -> HealthResponse:
    """Return deterministic process health without provider or data dependencies."""

    return HealthResponse()


@api_router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Process one OmniCare support request",
    tags=["chat"],
)
def chat(
    payload: ChatRequest,
    request: Request,
    flow: OmniCareSupportFlow = Depends(get_support_flow),
) -> ChatResponse:
    """Validate input, attach request context, and delegate to the support Flow."""

    return flow.run(
        user_id=payload.user_id,
        message=payload.message,
        request_id=getattr(request.state, "request_id", None),
    )
