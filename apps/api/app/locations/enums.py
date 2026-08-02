"""Stable location classifications and lifecycle states."""

from enum import StrEnum


class LocationType(StrEnum):
    PHYSICAL = "physical"
    SERVICE_AREA = "service_area"
    HYBRID = "hybrid"
    VIRTUAL = "virtual"


class LocationStatus(StrEnum):
    SETUP_REQUIRED = "setup_required"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED_TEMPORARILY = "closed_temporarily"
    CLOSED_PERMANENTLY = "closed_permanently"
    ARCHIVED = "archived"


class LocationLifecycleAction(StrEnum):
    ACTIVATE = "activate"
    PAUSE = "pause"
    CLOSE_TEMPORARILY = "close_temporarily"
    CLOSE_PERMANENTLY = "close_permanently"
    ARCHIVE = "archive"
