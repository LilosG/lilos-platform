"""Stable classifications for authorization requests and decisions."""

from enum import StrEnum


class AuthorizationReason(StrEnum):
    ALLOWED = "allowed"
    USER_INACTIVE = "user_inactive"
    ORGANIZATION_NOT_EFFECTIVE = "organization_not_effective"
    MEMBERSHIP_MISSING = "membership_missing"
    MEMBERSHIP_INACTIVE = "membership_inactive"
    LOCATION_NOT_FOUND = "location_not_found"
    PERMISSION_NOT_GRANTED = "permission_not_granted"
    EXPLICIT_DENY = "explicit_deny"
    INSUFFICIENT_ASSURANCE = "insufficient_assurance"
    CATALOG_INCONSISTENCY = "catalog_inconsistency"
