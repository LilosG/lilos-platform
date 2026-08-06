"""Typed contracts for platform-administration bootstrap routes."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.api.app.schemas import ResponseMeta


class PlatformOwnerBootstrapResult(BaseModel):
    """Idempotent owner-bootstrap outcome, mirroring ``scripts/provision_pilot_owner.py``."""

    model_config = ConfigDict(extra="forbid")

    user_profile_id: UUID
    user_profile_created: bool
    membership_id: UUID
    membership_created: bool
    owner_role_assignment_created: bool


class PlatformAdministratorGrantResult(BaseModel):
    """Idempotent platform-administrator grant outcome."""

    model_config = ConfigDict(extra="forbid")

    user_profile_id: UUID
    grant_id: UUID
    grant_created: bool


class PlatformAdministratorSelfStatus(BaseModel):
    """Self-scoped disclosure of the caller's own platform-administrator standing.

    Safe to expose to the caller about themselves (unlike the fail-closed,
    non-disclosing 403 that ``require_platform_administrator`` returns to
    protect *other* organizations' data): a principal always knows their own
    grant and assurance state elsewhere in this API already (``/api/v1/me``).
    Distinguishes "no grant" from "grant exists but needs a step-up" so the
    frontend can render a truthful, distinct state for each.
    """

    model_config = ConfigDict(extra="forbid")

    is_platform_administrator: bool
    meets_required_assurance: bool
    required_assurance_level: str


class PlatformAdministratorSelfStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: PlatformAdministratorSelfStatus
    meta: ResponseMeta
