"""Typed GBP API and domain contracts."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MappingConfirm(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    location_id: UUID
    write_enabled: bool = False


class ProfileChangeCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    base_snapshot_id: UUID
    desired_fields: dict[str, Any]
    approved_fact_revision_ids: list[UUID] = Field(min_length=1, max_length=50)


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    decision: Literal["approve", "reject"]
    expected_status: Literal["awaiting_approval"] = "awaiting_approval"


class PublishRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_run_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)
