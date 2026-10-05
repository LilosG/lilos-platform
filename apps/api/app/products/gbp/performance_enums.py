"""Typed vocabulary of the Business Profile Performance sync: metrics, runs and failure codes."""

from enum import StrEnum


class GBPPerformanceMetric(StrEnum):
    """Every daily metric the Business Profile Performance API provides (names are Google's)."""

    BUSINESS_IMPRESSIONS_DESKTOP_MAPS = "BUSINESS_IMPRESSIONS_DESKTOP_MAPS"
    BUSINESS_IMPRESSIONS_DESKTOP_SEARCH = "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH"
    BUSINESS_IMPRESSIONS_MOBILE_MAPS = "BUSINESS_IMPRESSIONS_MOBILE_MAPS"
    BUSINESS_IMPRESSIONS_MOBILE_SEARCH = "BUSINESS_IMPRESSIONS_MOBILE_SEARCH"
    CALL_CLICKS = "CALL_CLICKS"
    WEBSITE_CLICKS = "WEBSITE_CLICKS"
    BUSINESS_DIRECTION_REQUESTS = "BUSINESS_DIRECTION_REQUESTS"
    BUSINESS_CONVERSATIONS = "BUSINESS_CONVERSATIONS"
    BUSINESS_BOOKINGS = "BUSINESS_BOOKINGS"
    BUSINESS_FOOD_ORDERS = "BUSINESS_FOOD_ORDERS"
    BUSINESS_FOOD_MENU_CLICKS = "BUSINESS_FOOD_MENU_CLICKS"


# Profile views are the sum of the four impression metrics.
IMPRESSION_METRICS: tuple[GBPPerformanceMetric, ...] = (
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_DESKTOP_MAPS,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_DESKTOP_SEARCH,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_MAPS,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH,
)


# The actions every profile reports: a person called, visited the website or asked for directions.
ACTION_METRICS: tuple[GBPPerformanceMetric, ...] = (
    GBPPerformanceMetric.CALL_CLICKS,
    GBPPerformanceMetric.WEBSITE_CLICKS,
    GBPPerformanceMetric.BUSINESS_DIRECTION_REQUESTS,
)


class GBPPerformanceSyncStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    # Daily metrics were stored but the search keywords could not be read.
    PARTIAL = "partial"
    FAILED = "failed"


class GBPPerformanceSyncMode(StrEnum):
    BACKFILL = "backfill"
    RESYNC = "resync"


class GBPPerformanceFailureCode(StrEnum):
    INTEGRATION_NOT_FOUND = "GBP_INTEGRATION_NOT_FOUND"
    RECONNECT_REQUIRED = "INTEGRATION_RECONNECT_REQUIRED"
    SCOPE_REQUIRED = "GBP_SCOPE_REQUIRED"
    LOCATION_NOT_FOUND = "GBP_LOCATION_NOT_FOUND"
    LOCATION_AMBIGUOUS = "GBP_LOCATION_AMBIGUOUS"
    LOCATION_ID_INVALID = "LOCATION_ID_INVALID"
    LOCATION_ID_MISSING = "LOCATION_ID_MISSING"
    TOKEN_RESOLUTION_FAILED = "TOKEN_RESOLUTION_FAILED"
    PROVIDER_ACCESS_DENIED = "GBP_PERFORMANCE_ACCESS_DENIED"
    PROVIDER_REJECTED_REQUEST = "GBP_PERFORMANCE_REQUEST_REJECTED"
    PROVIDER_RATE_LIMITED = "GBP_PERFORMANCE_RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "GBP_PERFORMANCE_PROVIDER_UNAVAILABLE"
    PROVIDER_RESPONSE_INVALID = "GBP_PERFORMANCE_RESPONSE_INVALID"
    KEYWORDS_UNAVAILABLE = "GBP_PERFORMANCE_KEYWORDS_UNAVAILABLE"
    SYNC_FAILED = "GBP_PERFORMANCE_SYNC_FAILED"

    @property
    def retryable(self) -> bool:
        """Whether running the same sync again later can succeed without anyone acting."""
        return self in _RETRYABLE


_RETRYABLE = frozenset(
    {
        GBPPerformanceFailureCode.TOKEN_RESOLUTION_FAILED,
        GBPPerformanceFailureCode.PROVIDER_RATE_LIMITED,
        GBPPerformanceFailureCode.PROVIDER_UNAVAILABLE,
        GBPPerformanceFailureCode.PROVIDER_RESPONSE_INVALID,
        GBPPerformanceFailureCode.KEYWORDS_UNAVAILABLE,
        GBPPerformanceFailureCode.SYNC_FAILED,
    }
)


class GBPPerformanceAvailability(StrEnum):
    """What a performance number can be trusted to mean. Never rendered as 0 when not synced."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    NO_DATA = "no_data"
    NOT_SYNCED = "not_synced"
    NOT_CONNECTED = "not_connected"


def _check(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({','.join(repr(item.value) for item in values)})"


def enum_check(column: str, values: type[StrEnum]) -> str:
    return _check(column, values)
