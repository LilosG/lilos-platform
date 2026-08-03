"""Immutable internal contracts for deterministic authorization evaluation."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.enums import AuthorizationReason
from apps.api.app.schemas import ResponseMeta


class AuthorizationRequest(BaseModel):
    """Server-constructed policy request; never a client-controlled API body."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_user_id: UUID
    organization_id: UUID
    permission_key: Annotated[
        str,
        Field(
            min_length=3,
            max_length=100,
            pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
        ),
    ]
    resource_scope: ScopeType
    location_id: UUID | None = None
    minimum_assurance_level: AssuranceLevel = AssuranceLevel.AAL1

    @model_validator(mode="after")
    def validate_scope_identity(self) -> "AuthorizationRequest":
        if self.resource_scope is ScopeType.ORGANIZATION and self.location_id is not None:
            raise ValueError("organization scope forbids location_id")
        if self.resource_scope is ScopeType.LOCATION and self.location_id is None:
            raise ValueError("location scope requires location_id")
        return self


class AuthorizationDecision(BaseModel):
    """Detailed immutable decision retained only inside trusted application code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    organization_id: UUID
    platform_user_id: UUID
    membership_id: UUID | None
    permission_key: str
    resource_scope: ScopeType
    location_id: UUID | None
    assurance_level: AssuranceLevel
    minimum_assurance_level: AssuranceLevel
    applicable_role_assignment_ids: tuple[UUID, ...] = ()
    applicable_deny_ids: tuple[UUID, ...] = ()
    reason_code: AuthorizationReason


class AuthorizedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authorized: bool = True


class AuthorizedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: AuthorizedResult
    meta: ResponseMeta
