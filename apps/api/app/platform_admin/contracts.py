"""Typed contracts for platform-administration bootstrap routes."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.api.app.access_control.enums import InvitationStatus, MembershipStatus, MembershipType
from apps.api.app.authentication.enums import UserStatus
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


class SystemRole(StrEnum):
    """The fixed role catalog (``access_control.catalog.ROLE_CATALOG``), as codes."""

    ORGANIZATION_OWNER = "organization_owner"
    ORGANIZATION_ADMIN = "organization_admin"
    ORGANIZATION_MANAGER = "organization_manager"
    ORGANIZATION_MEMBER = "organization_member"
    ORGANIZATION_VIEWER = "organization_viewer"


class PendingInvitation(BaseModel):
    """The one pending invitation behind an ``invited`` membership, enough to cancel it."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: int
    status: InvitationStatus
    expires_at: datetime


class UserClientAccess(BaseModel):
    """One client a person can reach, with how."""

    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    organization_name: str
    membership_type: MembershipType
    membership_status: MembershipStatus
    roles: tuple[SystemRole, ...]
    invitation: PendingInvitation | None


class PlatformUser(BaseModel):
    """A person: name, email, standing and the clients they reach. Nothing else."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    display_name: str | None
    email: str | None
    status: UserStatus
    platform_administrator: bool
    access: tuple[UserClientAccess, ...]
    # How many clients the person reaches in all; `access` is capped, so the two can differ.
    access_total: int


class PlatformUserPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[PlatformUser, ...]
    limit: int
    offset: int
    next_offset: int | None
    has_more: bool


class PlatformUserListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: PlatformUserPage
    meta: ResponseMeta


class PlatformHealth(StrEnum):
    """A component's standing. ``unknown`` means it could not be read, never "fine"."""

    HEALTHY = "healthy"
    ATTENTION = "attention"
    UNKNOWN = "unknown"


class DeadLetterReason(StrEnum):
    """Why a job was given up on, from its final attempt."""

    PERMANENT_FAILURE = "permanent_failure"
    RETRIES_EXHAUSTED = "retries_exhausted"
    LEASE_EXPIRED = "lease_expired"
    TIMED_OUT = "timed_out"
    OUTCOME_UNCERTAIN = "outcome_uncertain"
    UNRECORDED = "unrecorded"


class DeadLetterGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: DeadLetterReason
    count: int


class DatabaseComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PlatformHealth


class SchedulerComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PlatformHealth
    active_schedules: int | None
    # The scheduled time of the most recent dispatch across active schedules.
    last_dispatch_at: datetime | None
    # None when it could not be judged.
    overdue: bool | None


class WorkerQueueComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PlatformHealth
    dead_letter_count: int | None
    dead_letter_groups: tuple[DeadLetterGroup, ...]
    # When the longest-waiting job that is already due became available.
    oldest_pending_at: datetime | None
    backlogged: bool | None


class FailedRunsComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PlatformHealth
    failed_last_24h: int | None


class IntegrationsComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PlatformHealth
    needing_attention: int | None


class SystemStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: PlatformHealth
    evaluated_at: datetime
    database: DatabaseComponent
    scheduler: SchedulerComponent
    worker_queue: WorkerQueueComponent
    failed_runs: FailedRunsComponent
    integrations: IntegrationsComponent


class SystemStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: SystemStatus
    meta: ResponseMeta
