"""Safe SEO-domain errors exposed through the standard API envelope."""

from http import HTTPStatus

from apps.api.app.errors import ApiError, ConflictError, NotFoundError
from apps.api.app.schemas import ErrorCategory


class SEOWebsiteNotFoundError(NotFoundError):
    code = "SEO_WEBSITE_NOT_FOUND"
    public_message = "The requested website was not found."


class SEOSearchPropertyNotConfiguredError(ConflictError):
    code = "SEO_SEARCH_PROPERTY_NOT_CONFIGURED"
    public_message = "No active, connected Search Console connection is configured."


class SEOSearchPropertyNotFoundError(NotFoundError):
    code = "SEO_SEARCH_PROPERTY_NOT_FOUND"
    public_message = "The requested Search Console property mapping was not found."


class SEOSearchConsoleScopeRequiredError(ConflictError):
    """The Google connection has not granted the Search Console OAuth scope."""

    code = "SEO_SEARCH_CONSOLE_SCOPE_REQUIRED"
    public_message = "Reconnect Google and authorize Search Console before discovering properties."


class SEOSearchConsoleDiscoveryFailedError(ApiError):
    """The Search Console discovery call to Google failed."""

    status_code = HTTPStatus.BAD_GATEWAY
    code = "SEO_SEARCH_CONSOLE_DISCOVERY_FAILED"
    category = ErrorCategory.SYSTEM
    retryable = True
    public_message = "Search Console property discovery failed."


class SEOOpportunityNotFoundError(NotFoundError):
    code = "SEO_OPPORTUNITY_NOT_FOUND"
    public_message = "The requested SEO opportunity was not found."


class SEORecommendationNotFoundError(NotFoundError):
    code = "SEO_RECOMMENDATION_NOT_FOUND"
    public_message = "The requested SEO recommendation was not found."


class SEORecommendationNotDecidableError(ConflictError):
    code = "SEO_RECOMMENDATION_NOT_DECIDABLE"
    public_message = "This recommendation is not in a state that can be decided."


class SEOImplementationTaskNotFoundError(NotFoundError):
    code = "SEO_IMPLEMENTATION_TASK_NOT_FOUND"
    public_message = "The requested SEO implementation task was not found."


class SEOCrawlTargetInvalidError(ConflictError):
    code = "SEO_CRAWL_TARGET_INVALID"
    public_message = "The crawl target is not within the confirmed website scope."


class SEOCrawlRunNotFoundError(NotFoundError):
    code = "SEO_CRAWL_RUN_NOT_FOUND"
    public_message = "The requested crawl run was not found."


class SEOQueryInvalidError(ConflictError):
    code = "SEO_QUERY_INVALID"
    public_message = "The SEO query parameters are invalid."
