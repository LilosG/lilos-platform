"""Typed industry commands and internal API response contracts."""

import re
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.policy_documents import PolicyValue, normalize_policy_document
from apps.api.app.schemas import ResponseMeta

INDUSTRY_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$", re.ASCII)


class IndustryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    key: Annotated[str, Field(min_length=3, max_length=63)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    default_configuration: dict[str, PolicyValue] = Field(default_factory=dict)
    default_risk_policy: dict[str, PolicyValue] = Field(default_factory=dict)
    default_content_policy: dict[str, PolicyValue] = Field(default_factory=dict)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if INDUSTRY_KEY_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "key must begin with a letter and contain lowercase letters, numbers, "
                "and single underscores only"
            )
        return value

    @field_validator(
        "default_configuration",
        "default_risk_policy",
        "default_content_policy",
        mode="before",
    )
    @classmethod
    def validate_policy(cls, value: Any) -> dict[str, PolicyValue]:
        return normalize_policy_document(value)


class IndustryTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_version: Annotated[int, Field(ge=1)]


class IndustryData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    key: str
    name: str
    status: IndustryStatus
    description: str | None
    default_configuration: dict[str, PolicyValue]
    default_risk_policy: dict[str, PolicyValue]
    default_content_policy: dict[str, PolicyValue]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    version: int


class IndustryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: IndustryData
    meta: ResponseMeta


class IndustryPagination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int
    offset: int
    next_offset: int | None
    has_more: bool


class IndustryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list[IndustryData]
    pagination: IndustryPagination
    meta: ResponseMeta
