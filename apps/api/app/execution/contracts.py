"""Immutable workflow execution contracts."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkflowSubmit(BaseModel):
    model_config = ConfigDict(frozen=True)
    workflow_version_id: UUID
    location_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)
    input_document: dict[str, Any] = Field(default_factory=dict)


class JobClaim(BaseModel):
    model_config = ConfigDict(frozen=True)
    worker_id: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=60, ge=5, le=3600)


class JobOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)
    result: Literal["succeeded", "retryable_failure", "permanent_failure", "ambiguous"]
    result_reference: str | None = Field(default=None, max_length=500)
    safe_error: str | None = Field(default=None, max_length=500)


class ScheduleCreate(BaseModel):
    """Command to create a recurring schedule for a known workflow type.

    ``workflow_key`` must be one of the keys in ``WORKFLOW_TYPES``.
    The ``workflow_version_id`` is resolved server-side by
    ``ExecutionService._resolve_workflow_version``.
    """

    model_config = ConfigDict(frozen=True)
    workflow_key: str = Field(min_length=3, max_length=128)
    key: str = Field(min_length=3, max_length=128)
    cron_expression: str = Field(min_length=5, max_length=100)
    timezone: str = Field(min_length=1, max_length=64)
    next_run_at: datetime
    location_id: UUID | None = None


class ScheduleUpdate(BaseModel):
    """Partial update for an existing schedule.

    At least one field must be provided. ``status`` changes (e.g.,
    ``active`` → ``paused``) are the most common update.
    """

    model_config = ConfigDict(frozen=True)
    status: Literal["active", "paused", "cancelled"] | None = None
    cron_expression: str | None = Field(default=None, min_length=5, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    next_run_at: datetime | None = None
