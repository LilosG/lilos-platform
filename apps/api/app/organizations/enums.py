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
