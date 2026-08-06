"""Typed organization-domain commands and API responses."""

import re
from datetime import datetime
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.app.domains.enums import OrganizationDomainStatus
from apps.api.app.schemas import ResponseMeta

DOMAIN_PATTERN = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
)


def normalize_domain(value: str) -> str:
    """Accept a bare hostname or a full URL and return a normalized hostname.

    Strips scheme, credentials, port, path, query, and fragment so an operator
    may paste either ``example.com`` or ``https://www.example.com/`` and get
    the same stored value for the same host.
    """
    candidate = value.strip().casefold()
    if "://" not in candidate:
        candidate = f"//{candidate}"
    parsed = urlsplit(candidate)
    host = (parsed.hostname or "").rstrip(".")
    return host


class OrganizationDomainCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: Annotated[str, Field(min_length=1, max_length=2_048)]
    is_primary: bool = False

    @field_validator("domain", mode="before")
    @classmethod
    def normalize(cls, value: Any) -> Any:
        if isinstance(value, str):
            return normalize_domain(value)
        return value

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        if not (3 <= len(value) <= 253) or DOMAIN_PATTERN.fullmatch(value) is None:
            raise ValueError("domain must be a valid registrable hostname, e.g. example.com")
        return value


class OrganizationDomainSetPrimary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_version: Annotated[int, Field(ge=1)]


class OrganizationDomainArchive(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_version: Annotated[int, Field(ge=1)]


class OrganizationDomainData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    organization_id: UUID
    domain: str
    is_primary: bool
    status: OrganizationDomainStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    version: int


class OrganizationDomainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: OrganizationDomainData
    meta: ResponseMeta


class OrganizationDomainListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list[OrganizationDomainData]
    meta: ResponseMeta
