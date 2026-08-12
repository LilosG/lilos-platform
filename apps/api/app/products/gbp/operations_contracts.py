"""Typed GBP operations (categories, hours, media, posts, suspension) contracts."""

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CapabilitySnapshotRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    capabilities: dict[str, Any]
    observed_at: str


class ChangeSetPropose(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    capability_key: str = Field(min_length=1, max_length=64)
    field_changes: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    evidence: dict[str, Any] = Field(default_factory=dict)
    risk: Literal["low", "medium", "high"] = "low"
    idempotency_key: str = Field(min_length=8, max_length=128)


class ChangeSetDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approve: bool


class SpecialHoursPeriod(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    opens: str
    closes: str


class SpecialHoursPropose(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    service_date: date
    periods: list[SpecialHoursPeriod] = Field(min_length=1, max_length=10)
    source: str = Field(min_length=1, max_length=64)


class MediaPropose(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    media_type: Literal["photo", "video", "logo", "cover"]
    source_reference: str = Field(min_length=1, max_length=1000)
    rights_authority: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)


class PostRevisionCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    post_key: UUID | None = None
    post_type: Literal["standard", "event", "offer", "alert"]
    content: str = Field(min_length=1, max_length=1500)
    call_to_action: dict[str, Any] | None = None
    event_or_offer: dict[str, Any] | None = None


class PostDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approve: bool


class PostPublishRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_run_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)


class SuspensionCaseReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    provider_status: str = Field(min_length=1, max_length=64)
    evidence_references: list[str] = Field(default_factory=list, max_length=50)


class MediaDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approve: bool


class MediaPublishRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_run_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)
