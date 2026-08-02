"""Typed location commands and internal API response contracts."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.schemas import ResponseMeta

LOCATION_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", re.ASCII)
RESERVED_LOCATION_SLUGS = frozenset(
    {"admin", "api", "internal", "platform", "public", "system", "support", "www"}
)

OptionalShort = Annotated[str, Field(min_length=1, max_length=200)] | None
OptionalAddress = Annotated[str, Field(min_length=1, max_length=200)] | None
OptionalEmail = (
    Annotated[
        str,
        Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"),
    ]
    | None
)


class LocationCreate(BaseModel):
    """Validated command for creating one setup-required location."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=1, max_length=200)]
    slug: Annotated[str, Field(min_length=3, max_length=63)]
    location_type: LocationType
    timezone: Annotated[str, Field(min_length=1, max_length=64)]
    address_line_1: OptionalAddress = None
    address_line_2: OptionalAddress = None
    city: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    region: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    postal_code: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    country_code: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    latitude: Annotated[Decimal, Field(ge=-90, le=90, max_digits=9, decimal_places=6)] | None = None
    longitude: (
        Annotated[Decimal, Field(ge=-180, le=180, max_digits=10, decimal_places=6)] | None
    ) = None
    service_area_description: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    phone: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    email: OptionalEmail = None
    website_url: AnyHttpUrl | None = None
    external_reference: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    is_primary: bool = False

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if LOCATION_SLUG_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "slug must begin with a letter and contain lowercase letters, numbers, "
                "and single hyphens only"
            )
        if value in RESERVED_LOCATION_SLUGS:
            raise ValueError("slug is reserved for platform routing")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("timezone must be a valid IANA timezone identifier") from exc
        return value

    @model_validator(mode="after")
    def validate_type_specific_fields(self) -> "LocationCreate":
        core_address = (self.address_line_1, self.city, self.region, self.postal_code)
        has_complete_address = all(value is not None for value in core_address)
        has_partial_address = any(value is not None for value in core_address)
        if self.location_type is LocationType.PHYSICAL and not has_complete_address:
            raise ValueError("physical locations require a complete address")
        if self.location_type is LocationType.SERVICE_AREA:
            if self.service_area_description is None:
                raise ValueError("service-area locations require a service-area description")
            if has_partial_address and not has_complete_address:
                raise ValueError("service-area address fields must be supplied together")
        if self.location_type is LocationType.HYBRID and (
            not has_complete_address or self.service_area_description is None
        ):
            raise ValueError("hybrid locations require a complete address and service area")
        if self.location_type is LocationType.VIRTUAL:
            if self.website_url is None:
                raise ValueError("virtual locations require a website URL")
            prohibited = (
                self.address_line_1,
                self.address_line_2,
                self.city,
                self.region,
                self.postal_code,
                self.latitude,
                self.longitude,
                self.service_area_description,
            )
            if any(value is not None for value in prohibited):
                raise ValueError("virtual locations cannot contain address or service-area fields")
        return self


class LocationTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_version: Annotated[int, Field(ge=1)]


class LocationData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    location_type: LocationType
    status: LocationStatus
    timezone: str
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    country_code: str
    latitude: Decimal | None
    longitude: Decimal | None
    service_area_description: str | None
    phone: str | None
    email: str | None
    website_url: str | None
    external_reference: str | None
    is_primary: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class LocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: LocationData
    meta: ResponseMeta


class LocationPagination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int
    offset: int
    next_offset: int | None
    has_more: bool


class LocationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list[LocationData]
    pagination: LocationPagination
    meta: ResponseMeta
