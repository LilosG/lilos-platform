from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DraftCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    review_revision_id: UUID
    response_text: str = Field(min_length=1, max_length=5000)
    generated_by_type: Literal["user", "ai", "template"] = "user"
    approved_fact_revision_ids: list[UUID] = Field(min_length=1, max_length=50)
    ai_execution_id: UUID | None = None


class PublishResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)
