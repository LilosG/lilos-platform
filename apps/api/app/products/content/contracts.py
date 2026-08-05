from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OpportunityCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    location_id: UUID | None = None
    product_key: str = Field(min_length=1, max_length=64)
    target_reference: str = Field(min_length=1, max_length=500)
    opportunity_type: str = Field(min_length=1, max_length=64)
    source_type: str = Field(min_length=1, max_length=64)
    source_reference: str = Field(min_length=1, max_length=500)
    evidence_document: dict[str, Any]
    priority_score: int = Field(ge=0, le=100)


class OpportunityDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    accept: bool


class ItemCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    opportunity_id: UUID | None = None
    location_id: UUID | None = None
    content_type: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=300)
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BriefCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    audience: str = Field(min_length=1, max_length=500)
    intent: str = Field(min_length=1, max_length=100)
    target_reference: str = Field(min_length=1, max_length=500)
    approved_fact_revision_ids: list[UUID] = Field(min_length=1, max_length=100)
    required_claims: list[str] = Field(default_factory=list, max_length=100)
    prohibited_claims: list[str] = Field(default_factory=list, max_length=100)
    required_local_references: list[str] = Field(default_factory=list, max_length=100)
    source_evidence_references: list[str] = Field(default_factory=list, max_length=100)
    validation_requirements: dict[str, Any] = Field(default_factory=dict)


class AIDraftCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    brief_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)


class RevisionCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    body: str = Field(min_length=1, max_length=200000)
    frontmatter: dict[str, Any]
    created_by_type: Literal["user", "ai"]
    approved_fact_revision_ids: list[UUID] = Field(min_length=1, max_length=100)
    ai_execution_id: UUID | None = None
    prohibited_claims: list[str] = Field(default_factory=list, max_length=100)


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stage: Literal["editorial", "client"]
    approve: bool


class PublicationCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    publishing_target_id: UUID
    workflow_run_id: UUID
    target_path: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)
