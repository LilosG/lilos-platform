"""Minimal process health endpoints."""

from fastapi import APIRouter, Request

from apps.api.app.config import Settings
from apps.api.app.errors import request_correlation_id
from apps.api.app.schemas import (
    HealthStatus,
    LivenessData,
    LivenessResponse,
    ReadinessData,
    ReadinessResponse,
    ResponseMeta,
)

router = APIRouter(prefix="/health", tags=["health"])


def settings_from_request(request: Request) -> Settings:
    """Return the immutable settings attached by the application factory."""
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("API settings are unavailable")
    return settings


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Check API process liveness",
)
async def live(request: Request) -> LivenessResponse:
    """Report only whether the API process is running."""
    settings = settings_from_request(request)
    return LivenessResponse(
        data=LivenessData(service=settings.service_name, status=HealthStatus.ALIVE),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Check API process readiness",
)
async def ready(request: Request) -> ReadinessResponse:
    """Report readiness using only dependencies that are currently implemented."""
    settings = settings_from_request(request)
    return ReadinessResponse(
        data=ReadinessData(
            service=settings.service_name,
            status=HealthStatus.READY,
            dependencies=[],
        ),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )
