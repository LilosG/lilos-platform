"""Typed Content enums shared across contracts, models and services."""

from enum import StrEnum


class ContentTargetKind(StrEnum):
    """Whether a brief improves an attributed existing page or proposes a new URL."""

    EXISTING_PAGE = "existing_page"
    NEW_PAGE = "new_page"


class ComposeContentType(StrEnum):
    """Types an operator may pin when composing from a prompt; absent means Hermes decides."""

    BLOG_POST = "blog_post"
    LISTICLE = "listicle"
    LANDING_PAGE = "landing_page"
    SERVICE_PAGE = "service_page"
    LOCATION_PAGE = "location_page"
    GUIDE = "guide"


class ComposeFailureCode(StrEnum):
    """Why a compose run produced no draft. Persisted as the run's failure code."""

    WEBSITE_NOT_CRAWLED = "CONTENT_WEBSITE_NOT_CRAWLED"
    PLAN_INVALID = "CONTENT_PLAN_INVALID"
    BELOW_QUALITY_FLOOR = "CONTENT_BELOW_QUALITY_FLOOR"
    TOPIC_OVERLAP = "CONTENT_TOPIC_OVERLAP"
