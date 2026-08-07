"""Safe Analytics-domain errors exposed through the standard API envelope."""

from http import HTTPStatus

from apps.api.app.errors import ApiError, ConflictError, NotFoundError
from apps.api.app.schemas import ErrorCategory


class AnalyticsNotConfiguredError(ConflictError):
    code = "ANALYTICS_NOT_CONFIGURED"
    public_message = "No active, connected Google Analytics connection is configured."


class AnalyticsScopeRequiredError(ConflictError):
    """The Google connection has not granted the Analytics OAuth scope."""

    code = "ANALYTICS_SCOPE_REQUIRED"
    public_message = "Reconnect Google and authorize Analytics before discovering properties."


class AnalyticsDiscoveryFailedError(ApiError):
    """The GA4 discovery call to Google failed."""

    status_code = HTTPStatus.BAD_GATEWAY
    code = "ANALYTICS_DISCOVERY_FAILED"
    category = ErrorCategory.SYSTEM
    retryable = True
    public_message = "Google Analytics property discovery failed."


class AnalyticsPropertyNotFoundError(NotFoundError):
    code = "ANALYTICS_PROPERTY_NOT_FOUND"
    public_message = "The requested Analytics property mapping was not found."
