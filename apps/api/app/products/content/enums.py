"""Typed Content enums shared across contracts, models and services."""

from enum import StrEnum


class ContentTargetKind(StrEnum):
    """Whether a brief improves an attributed existing page or proposes a new URL."""

    EXISTING_PAGE = "existing_page"
    NEW_PAGE = "new_page"
