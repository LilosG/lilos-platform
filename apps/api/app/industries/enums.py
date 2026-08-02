"""Stable industry lifecycle values."""

from enum import StrEnum


class IndustryStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class IndustryLifecycleAction(StrEnum):
    DEPRECATE = "deprecate"
    REACTIVATE = "reactivate"
    ARCHIVE = "archive"
