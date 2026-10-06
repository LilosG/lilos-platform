"""Stable organization classifications and lifecycle states."""

from enum import StrEnum


class OrganizationType(StrEnum):
    """Supported organization ownership categories."""

    CLIENT = "client"
    INTERNAL = "internal"
    PARTNER = "partner"
    DEMO = "demo"
    TEST = "test"


class OrganizationStatus(StrEnum):
    """Supported organization lifecycle states."""

    PROSPECT = "prospect"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    OFFBOARDING = "offboarding"
    ARCHIVED = "archived"


class OrganizationLifecycleAction(StrEnum):
    """Explicit administrative actions that move organization lifecycle state."""

    START_ONBOARDING = "start_onboarding"
    ACTIVATE = "activate"
    PAUSE = "pause"
    RESUME = "resume"
    SUSPEND = "suspend"
    START_OFFBOARDING = "start_offboarding"
    ARCHIVE = "archive"


class OrganizationRemovalState(StrEnum):
    """Where a permanent-removal request stands, as reported to the caller."""

    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class OrganizationRemovalErrorCode(StrEnum):
    """Stable codes for refusing a removal request; the UI chooses its message from these."""

    REQUIRES_ARCHIVED = "ORGANIZATION_REMOVAL_REQUIRES_ARCHIVED"
    CONFIRMATION_MISMATCH = "ORGANIZATION_REMOVAL_CONFIRMATION_MISMATCH"
