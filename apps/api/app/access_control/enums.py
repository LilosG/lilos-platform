"""Stable membership, invitation, role, and scope classifications."""

from enum import StrEnum


class MembershipType(StrEnum):
    INTERNAL = "internal"
    CLIENT = "client"
    PARTNER = "partner"
    SUPPORT = "support"


class MembershipStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class MembershipAction(StrEnum):
    ACTIVATE = "activate"
    SUSPEND = "suspend"
    RESTORE = "restore"
    REVOKE = "revoke"
    EXPIRE = "expire"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ScopeType(StrEnum):
    ORGANIZATION = "organization"
    LOCATION = "location"


class RoleStatus(StrEnum):
    ACTIVE = "active"
