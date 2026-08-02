"""Typed organization commands and API response contracts."""

import re
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.schemas import ResponseMeta

ORGANIZATION_SLUG_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
    re.ASCII,
)
RESERVED_ORGANIZATION_SLUGS = frozenset(
    {"admin", "api", "internal", "platform", "public", "system", "support", "www"}
)

OrganizationSlug = Annotated[str, Field(min_length=3, max_length=63)]
OrganizationName = Annotated[str, Field(min_length=1, max_length=200)]
OptionalName = Annotated[str, Field(min_length=1, max_length=200)] | None
EmailReference = Annotated[
    str,
    Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"),
]


class OrganizationCreate(BaseModel):
    """Validated command for creating an organization in prospect state."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: OrganizationName
    slug: OrganizationSlug
    organization_type: OrganizationType
    timezone: Annotated[str, Field(min_length=1, max_length=64)]
    default_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    legal_name: OptionalName = None
    website_url: AnyHttpUrl | None = None
    primary_contact_name: OptionalName = None
    primary_contact_email: EmailReference | None = None
    primary_contact_phone: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    billing_email: EmailReference | None = None
    external_reference: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    onboarding_status: Annotated[str, Field(min_length=1, max_length=64)] | None = None

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: Any) -> Any:
        """Normalize only surrounding whitespace and ASCII letter case."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        """Reject malformed or routing-reserved organization slugs."""
        if ORGANIZATION_SLUG_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "slug must begin with a letter and contain lowercase letters, numbers, "
                "and single hyphens only"
            )
        if value in RESERVED_ORGANIZATION_SLUGS:
            raise ValueError("slug is reserved for platform routing")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Require an identifier available in the IANA timezone database."""
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("timezone must be a valid IANA timezone identifier") from exc
        return value

    @field_serializer("website_url")
    def serialize_website_url(self, value: AnyHttpUrl | None) -> str | None:
        """Serialize validated URLs as their normalized string representation."""
        return str(value) if value is not None else None


class OrganizationTransition(BaseModel):
    """Optimistic-concurrency precondition for one lifecycle action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_version: Annotated[int, Field(ge=1)]


class OrganizationData(BaseModel):
    """Stable internal administrative representation of an organization."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    name: str
    slug: str
    organization_type: OrganizationType
    status: OrganizationStatus
    timezone: str
    default_currency: str
    legal_name: str | None
    website_url: str | None
    primary_contact_name: str | None
    primary_contact_email: str | None
    primary_contact_phone: str | None
    billing_email: str | None
    external_reference: str | None
    onboarding_status: str | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class OrganizationResponse(BaseModel):
    """Single-organization success envelope."""

    model_config = ConfigDict(extra="forbid")

    data: OrganizationData
    meta: ResponseMeta


class OrganizationPagination(BaseModel):
    """Deterministic bounded offset-pagination metadata."""

    model_config = ConfigDict(extra="forbid")

    limit: int
    offset: int
    next_offset: int | None
    has_more: bool


class OrganizationListResponse(BaseModel):
    """Organization collection success envelope."""

    model_config = ConfigDict(extra="forbid")

    data: list[OrganizationData]
    pagination: OrganizationPagination
    meta: ResponseMeta
