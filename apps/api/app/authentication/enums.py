"""Stable authentication and platform-user classifications."""

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class AssuranceLevel(StrEnum):
    AAL1 = "aal1"
    AAL2 = "aal2"


class UserLifecycleAction(StrEnum):
    DEACTIVATE = "deactivate"
    REACTIVATE = "reactivate"
