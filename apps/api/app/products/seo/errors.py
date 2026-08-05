"""Safe SEO-domain errors exposed through the standard API envelope."""

from apps.api.app.errors import ConflictError, NotFoundError


class SEOWebsiteNotFoundError(NotFoundError):
    code = "SEO_WEBSITE_NOT_FOUND"
    public_message = "The requested website was not found."


class SEOSearchPropertyNotConfiguredError(ConflictError):
    code = "SEO_SEARCH_PROPERTY_NOT_CONFIGURED"
    public_message = "No active, connected Search Console connection is configured."


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


class SEOQueryInvalidError(ConflictError):
    code = "SEO_QUERY_INVALID"
    public_message = "The SEO query parameters are invalid."
