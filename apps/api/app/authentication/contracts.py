"""Typed platform-user, verified-token, and principal contracts."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.schemas import ResponseMeta


class UserProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    auth_user_id: UUID
    email: Annotated[str, Field(min_length=3, max_length=254)] | None = None
    display_name: Annotated[str, Field(min_length=1, max_length=200)] | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        if "@" not in normalized or any(character.isspace() for character in normalized):
            raise ValueError("email must be a valid administrative contact reference")
        return normalized


class UserLifecycleCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_version: Annotated[int, Field(ge=1)]


class UserProfileData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    auth_user_id: UUID
    email: str | None
    display_name: str | None
    status: UserStatus
    deactivated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: UserProfileData
    meta: ResponseMeta


class VerifiedProviderClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    auth_user_id: UUID
    session_id: UUID
    assurance_level: AssuranceLevel
    issued_at: datetime | None
    expires_at: datetime
    algorithm: str
    key_id: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("issued_at", "expires_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("token timestamps must be timezone-aware")
        return value.astimezone(UTC)


class AuthenticatedPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_user_id: UUID
    auth_user_id: UUID
    user_status: UserStatus
    session_id: UUID
    assurance_level: AssuranceLevel
    token_issued_at: datetime | None
    token_expires_at: datetime


class AuthenticatedPrincipalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: AuthenticatedPrincipal
    meta: ResponseMeta
