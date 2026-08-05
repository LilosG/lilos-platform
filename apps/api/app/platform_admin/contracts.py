"""Typed contracts for platform-administration bootstrap routes."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlatformOwnerBootstrapResult(BaseModel):
    """Idempotent owner-bootstrap outcome, mirroring ``scripts/provision_pilot_owner.py``."""

    model_config = ConfigDict(extra="forbid")

    user_profile_id: UUID
    user_profile_created: bool
    membership_id: UUID
    membership_created: bool
    owner_role_assignment_created: bool
