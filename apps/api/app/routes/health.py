"""Minimal process health endpoints."""

from http import HTTPStatus

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apps.api.app.config import Settings
from apps.api.app.database.health import check_database_health
from apps.api.app.database.session import database_runtime_from_request
from apps.api.app.errors import request_correlation_id
from apps.api.app.schemas import (
    DependencyHealth,
    DependencyStatus,
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
async def ready(request: Request) -> JSONResponse:
    """Report whether PostgreSQL is available for database-backed work."""
    settings = settings_from_request(request)
    database_health = await check_database_health(database_runtime_from_request(request))
    response = ReadinessResponse(
        data=ReadinessData(
            service=settings.service_name,
            status=HealthStatus.READY if database_health.available else HealthStatus.NOT_READY,
            dependencies=[
                DependencyHealth(
                    name="postgresql",
                    status=(
                        DependencyStatus.HEALTHY
                        if database_health.available
                        else DependencyStatus.UNAVAILABLE
                    ),
                )
            ],
        ),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )
    return JSONResponse(
        status_code=HTTPStatus.OK if database_health.available else HTTPStatus.SERVICE_UNAVAILABLE,
        content=response.model_dump(mode="json"),
    )
