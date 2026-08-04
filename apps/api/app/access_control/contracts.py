"""Typed contracts for memberships, invitations, catalog records, and scopes."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.api.app.access_control.enums import (
    InvitationStatus,
    MembershipStatus,
    MembershipType,
    RoleStatus,
    ScopeType,
)
from apps.api.app.schemas import ResponseMeta


class MembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    user_profile_id: UUID
    membership_type: MembershipType


class MembershipLifecycleCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_version: Annotated[int, Field(ge=1)]


class MembershipData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    organization_id: UUID
    user_profile_id: UUID
    membership_type: MembershipType
    status: MembershipStatus
    invited_at: datetime | None
    activated_at: datetime | None
    suspended_at: datetime | None
    revoked_at: datetime | None
    expired_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class MembershipResponse(BaseModel):
    data: MembershipData
    meta: ResponseMeta


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    user_profile_id: UUID
    email: Annotated[str, Field(min_length=3, max_length=320)]
    membership_type: MembershipType
    invited_by_user_profile_id: UUID
    lifetime_days: Annotated[int, Field(ge=1, le=30)] = 7

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        local, separator, domain = normalized.rpartition("@")
        if (
            normalized.count("@") != 1
            or not separator
            or not local
            or "." not in domain
            or any(c.isspace() for c in normalized)
        ):
            raise ValueError("email must use bounded email syntax")
        return normalized


class InvitationIssue(BaseModel):
    """Local/test invitation command whose actor is derived from authentication."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    user_profile_id: UUID
    email: Annotated[str, Field(min_length=3, max_length=320)]
    membership_type: MembershipType
    lifetime_days: Annotated[int, Field(ge=1, le=30)] = 7

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return InvitationCreate.normalize_email(value)


class InvitationData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    organization_id: UUID
    membership_id: UUID
    normalized_email: str
    status: InvitationStatus
    expires_at: datetime
    invited_by_user_profile_id: UUID
    accepted_by_user_profile_id: UUID | None
    accepted_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class InvitationResponse(BaseModel):
    data: InvitationData
    meta: ResponseMeta


class InvitationCreatedData(InvitationData):
    invitation_token: str


class InvitationCreatedResponse(BaseModel):
    data: InvitationCreatedData
    meta: ResponseMeta


class InvitationAccept(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    token: Annotated[str, Field(max_length=128)]


class ScopedPermissionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope_type: ScopeType
    location_id: UUID | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "ScopedPermissionCommand":
        if (self.scope_type is ScopeType.ORGANIZATION) != (self.location_id is None):
            raise ValueError("organization scope forbids and location scope requires location_id")
        return self


class RoleAssignmentCreate(ScopedPermissionCommand):
    role_id: UUID


class PermissionDenyCreate(ScopedPermissionCommand):
    permission_id: UUID


class RoleData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    key: str
    name: str
    description: str
    status: RoleStatus
    is_system: bool
    created_at: datetime
    updated_at: datetime
    version: int


class PermissionData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    key: str
    name: str
    description: str
    resource: str
    action: str
    created_at: datetime


class CatalogResponse(BaseModel):
    data: list[RoleData] | list[PermissionData]
    meta: ResponseMeta


class AssignmentData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    organization_id: UUID
    membership_id: UUID
    role_id: UUID
    scope_type: ScopeType
    location_id: UUID | None
    created_at: datetime


class DenyData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    organization_id: UUID
    membership_id: UUID
    permission_id: UUID
    scope_type: ScopeType
    location_id: UUID | None
    created_at: datetime


class AccessMutationResponse(BaseModel):
    data: AssignmentData | DenyData
    meta: ResponseMeta


class BootstrapOwnerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    user_profile_id: UUID
    membership_type: MembershipType


class MyOrganizationData(BaseModel):
    """Self-scoped organization-membership summary for the authenticated caller."""

    model_config = ConfigDict(extra="forbid")
    organization_id: UUID
    organization_name: str
    organization_slug: str
    organization_status: str
    membership_id: UUID
    membership_status: MembershipStatus
    membership_type: MembershipType


class MyOrganizationsResponse(BaseModel):
    data: list[MyOrganizationData]
    meta: ResponseMeta
