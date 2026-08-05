"""Typed request contracts for GBP OAuth integration routes."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MappingCreate(Contract):
    """Bind a discovered Google Business Profile location to a platform resource."""

    connection_id: UUID
    external_resource_id: Annotated[str, Field(min_length=1, max_length=500)]
    platform_resource_id: UUID | None = None
