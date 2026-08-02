"""Shared, typed API response contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Strict base model for public API contracts."""

    model_config = ConfigDict(extra="forbid")


class ResponseMeta(ApiModel):
    """Metadata returned with API response bodies."""

    correlation_id: str


class HealthStatus(StrEnum):
    """Stable health states exposed by the API."""

    ALIVE = "alive"
    READY = "ready"
    NOT_READY = "not_ready"


class DependencyStatus(StrEnum):
    """Stable dependency states for implemented readiness checks."""

    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"


class DependencyHealth(ApiModel):
    """Status for a dependency that is currently implemented and required."""

    name: str
    status: DependencyStatus


class LivenessData(ApiModel):
    """Minimal process liveness information."""

    service: str
    status: HealthStatus


class LivenessResponse(ApiModel):
    """Liveness endpoint response."""

    data: LivenessData
    meta: ResponseMeta


class ReadinessData(ApiModel):
    """API readiness and only its currently implemented required dependencies."""

    service: str
    status: HealthStatus
    dependencies: list[DependencyHealth]


class ReadinessResponse(ApiModel):
    """Readiness endpoint response."""

    data: ReadinessData
    meta: ResponseMeta


class ErrorCategory(StrEnum):
    """Stable error categories available to API consumers."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    SYSTEM = "system"


class ErrorDetail(ApiModel):
    """A safe, client-facing error detail."""

    field: str | None = None
    code: str
    message: str


class ErrorBody(ApiModel):
    """Machine-readable API error information."""

    code: str
    message: str
    category: ErrorCategory
    retryable: bool
    details: list[ErrorDetail]


class ErrorResponse(ApiModel):
    """Standard JSON API error envelope."""

    error: ErrorBody
    meta: ResponseMeta
