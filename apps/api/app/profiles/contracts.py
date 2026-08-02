"""Typed profile creation, replacement, and internal API contracts."""

from datetime import datetime
from typing import Annotated, Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.api.app.profiles.validation import normalize_string_collection, reject_claim_overlap
from apps.api.app.schemas import ResponseMeta

ShortText = Annotated[str, Field(min_length=1, max_length=200)]
SummaryText = Annotated[str, Field(min_length=1, max_length=1_000)]
ContextText = Annotated[str, Field(min_length=1, max_length=4_000)]
LongContextText = Annotated[str, Field(min_length=1, max_length=8_000)]


class ControlledProfileContent(BaseModel):
    """Shared validation behavior for mutable controlled profile content."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    collection_limits: ClassVar[dict[str, int]]

    @field_validator("*", mode="before")
    @classmethod
    def normalize_collections(cls, value: Any, info: Any) -> Any:
        limit = cls.collection_limits.get(info.field_name)
        if limit is None:
            return value
        return normalize_string_collection(
            value,
            field_name=info.field_name,
            item_max_length=limit,
        )

    @model_validator(mode="after")
    def claims_do_not_conflict(self) -> "ControlledProfileContent":
        reject_claim_overlap(
            getattr(self, "approved_claims", None),
            getattr(self, "prohibited_claims", None),
        )
        return self


class OrganizationProfileCreate(ControlledProfileContent):
    collection_limits = {
        "primary_services": 500,
        "approved_claims": 500,
        "prohibited_claims": 500,
        "tone_guidelines": 500,
        "legal_disclaimers": 2_000,
    }

    brand_name: ShortText | None = None
    brand_summary: SummaryText | None = None
    business_description: LongContextText | None = None
    value_proposition: ContextText | None = None
    target_customer: ContextText | None = None
    primary_services: list[str] | None = None
    approved_claims: list[str] | None = None
    prohibited_claims: list[str] | None = None
    tone_guidelines: list[str] | None = None
    legal_disclaimers: list[str] | None = None
    default_call_to_action: SummaryText | None = None


class OrganizationProfileReplace(OrganizationProfileCreate):
    expected_version: Annotated[int, Field(ge=1)]


class LocationProfileCreate(ControlledProfileContent):
    collection_limits = {
        "primary_services": 500,
        "local_landmarks": 500,
        "local_references": 500,
        "approved_claims": 500,
        "prohibited_claims": 500,
        "tone_overrides": 500,
    }

    local_description: LongContextText | None = None
    primary_services: list[str] | None = None
    service_area: ContextText | None = None
    local_landmarks: list[str] | None = None
    local_references: list[str] | None = None
    approved_claims: list[str] | None = None
    prohibited_claims: list[str] | None = None
    tone_overrides: list[str] | None = None
    call_to_action_override: SummaryText | None = None


class LocationProfileReplace(LocationProfileCreate):
    expected_version: Annotated[int, Field(ge=1)]


class OrganizationProfileData(OrganizationProfileCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime
    version: int


class LocationProfileData(LocationProfileCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    organization_id: UUID
    location_id: UUID
    created_at: datetime
    updated_at: datetime
    version: int


class OrganizationProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: OrganizationProfileData
    meta: ResponseMeta


class LocationProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: LocationProfileData
    meta: ResponseMeta
