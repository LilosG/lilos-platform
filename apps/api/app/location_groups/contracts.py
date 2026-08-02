"""Typed location-group commands and internal API responses."""

import re
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.app.location_groups.enums import LocationGroupStatus
from apps.api.app.schemas import ResponseMeta

LOCATION_GROUP_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", re.ASCII)
RESERVED_LOCATION_GROUP_KEYS = frozenset(
    {"admin", "api", "internal", "platform", "public", "system", "support", "www"}
)


class LocationGroupContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(min_length=1, max_length=1_000)] | None = None

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class LocationGroupCreate(LocationGroupContent):
    key: Annotated[str, Field(min_length=3, max_length=63)]

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if LOCATION_GROUP_KEY_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "key must begin with a letter and contain lowercase letters, numbers, "
                "and single hyphens only"
            )
        if value in RESERVED_LOCATION_GROUP_KEYS:
            raise ValueError("key is reserved for platform routing")
        return value


class LocationGroupReplace(LocationGroupContent):
    expected_version: Annotated[int, Field(ge=1)]


class LocationGroupArchive(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_version: Annotated[int, Field(ge=1)]


class LocationGroupData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    organization_id: UUID
    name: str
    key: str
    description: str | None
    status: LocationGroupStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    version: int


class LocationGroupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: LocationGroupData
    meta: ResponseMeta


class LocationGroupPagination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int
    offset: int
    next_offset: int | None
    has_more: bool


class LocationGroupListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list[LocationGroupData]
    pagination: LocationGroupPagination
    meta: ResponseMeta


class LocationGroupMembershipData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    organization_id: UUID
    location_group_id: UUID
    location_id: UUID
    created_at: datetime


class LocationGroupMembershipResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: LocationGroupMembershipData
    meta: ResponseMeta


class LocationGroupMembershipListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list[LocationGroupMembershipData]
    pagination: LocationGroupPagination
    meta: ResponseMeta
