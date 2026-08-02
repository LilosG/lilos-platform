"""Immutable contracts for the computed business-identity read model."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.schemas import ResponseMeta


class ImmutableIdentityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)


class OrganizationIdentity(ImmutableIdentityContract):
    id: UUID
    name: str
    slug: str
    organization_type: OrganizationType
    status: OrganizationStatus
    timezone: str
    default_currency: str
    version: int


class LocationIdentity(ImmutableIdentityContract):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    location_type: LocationType
    status: LocationStatus
    timezone: str
    country_code: str
    is_primary: bool
    version: int


class IndustryIdentity(ImmutableIdentityContract):
    id: UUID
    key: str
    name: str
    status: IndustryStatus
    version: int


class OrganizationProfileIdentity(ImmutableIdentityContract):
    id: UUID
    version: int
    brand_name: str | None
    brand_summary: str | None
    business_description: str | None
    value_proposition: str | None
    target_customer: str | None
    primary_services: tuple[str, ...] | None
    approved_claims: tuple[str, ...] | None
    prohibited_claims: tuple[str, ...] | None
    tone_guidelines: tuple[str, ...] | None
    legal_disclaimers: tuple[str, ...] | None
    default_call_to_action: str | None


class LocationProfileIdentity(ImmutableIdentityContract):
    id: UUID
    version: int
    local_description: str | None
    primary_services: tuple[str, ...] | None
    service_area: str | None
    local_landmarks: tuple[str, ...] | None
    local_references: tuple[str, ...] | None
    approved_claims: tuple[str, ...] | None
    prohibited_claims: tuple[str, ...] | None
    tone_overrides: tuple[str, ...] | None
    call_to_action_override: str | None


class ScalarSource(StrEnum):
    ORGANIZATION_PROFILE = "organization_profile"
    LOCATION_PROFILE = "location_profile"
    NONE = "none"


class ResolvedCallToAction(ImmutableIdentityContract):
    value: str | None
    source: ScalarSource


class OrganizationBusinessIdentity(ImmutableIdentityContract):
    organization: OrganizationIdentity
    industry: IndustryIdentity | None
    organization_profile: OrganizationProfileIdentity | None
    has_industry: bool
    has_organization_profile: bool


class LocationBusinessIdentity(OrganizationBusinessIdentity):
    location: LocationIdentity
    location_profile: LocationProfileIdentity | None
    has_location_profile: bool
    resolved_call_to_action: ResolvedCallToAction


class OrganizationBusinessIdentityResponse(ImmutableIdentityContract):
    data: OrganizationBusinessIdentity
    meta: ResponseMeta


class LocationBusinessIdentityResponse(ImmutableIdentityContract):
    data: LocationBusinessIdentity
    meta: ResponseMeta
