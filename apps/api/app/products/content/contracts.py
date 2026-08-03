from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
