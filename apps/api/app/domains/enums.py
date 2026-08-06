"""Stable organization-domain classifications."""

from enum import StrEnum


class OrganizationDomainStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
