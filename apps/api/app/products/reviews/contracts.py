from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.app.execution.automations import RunStatus


class DraftCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    review_revision_id: UUID
    response_text: str = Field(min_length=1, max_length=5000)
    generated_by_type: Literal["user", "ai", "template"] = "user"
    approved_fact_revision_ids: list[UUID] = Field(default_factory=list, max_length=100)
    ai_execution_id: UUID | None = None


class PublishResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)


class AIDraftCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    review_revision_id: UUID
    approved_fact_revision_ids: list[UUID] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ReviewIngestResult(StrEnum):
    """How a finished manual review import ended."""

    SUCCEEDED = "SUCCEEDED"
    RECONNECT_REQUIRED = "RECONNECT_REQUIRED"
    FAILED = "FAILED"


class ReviewIngestRun(BaseModel):
    """A queued or running manual review import."""

    model_config = ConfigDict(frozen=True)
    run_id: UUID
    run_status: RunStatus


class ReviewIngestStatus(ReviewIngestRun):
    """A manual review import; ``result`` is set only once it has finished."""

    result: ReviewIngestResult | None
