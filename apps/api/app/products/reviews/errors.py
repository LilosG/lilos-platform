"""Safe Reviews-domain errors exposed through the standard API envelope."""

from apps.api.app.errors import ConflictError, NotFoundError


class ReviewNotFoundError(NotFoundError):
    """A review identifier does not exist for this organization."""

    code = "REVIEW_NOT_FOUND"
    public_message = "The requested review was not found."


class ReviewRevisionNotFoundError(NotFoundError):
    """A review revision identifier does not exist for this organization."""

    code = "REVIEW_REVISION_NOT_FOUND"
    public_message = "The requested review revision was not found."


class UnsafeDraftError(ConflictError):
    """A response draft failed policy validation."""

    code = "REVIEW_DRAFT_UNSAFE"
    public_message = "The response draft did not pass policy validation."


class GroundingRequiredError(ConflictError):
    """A response draft was submitted without approved business-fact grounding."""

    code = "REVIEW_DRAFT_GROUNDING_REQUIRED"
    public_message = "Approved business-fact grounding is required."


class ResponseNotApprovalEligibleError(ConflictError):
    """A response is not in a state that can be approved."""

    code = "REVIEW_RESPONSE_NOT_APPROVAL_ELIGIBLE"
    public_message = "The current response is not eligible for approval."


class ReviewChangedAfterDraftError(ConflictError):
    """The underlying review changed after the response was drafted."""

    code = "REVIEW_CHANGED_AFTER_DRAFT"
    public_message = "The review changed after this response was drafted."


class ResponseNotPublishEligibleError(ConflictError):
    """A response is not in a state that can be published."""

    code = "REVIEW_RESPONSE_NOT_PUBLISH_ELIGIBLE"
    public_message = "An approved response is required before publication."


class RestrictedReviewCannotAutoPublishError(ConflictError):
    """A restricted (escalated) review cannot be auto-published."""

    code = "REVIEW_RESTRICTED_CANNOT_AUTO_PUBLISH"
    public_message = "This review is restricted and cannot be auto-published."


class InvalidReviewQueryError(ConflictError):
    """A review list query used an out-of-bounds pagination value."""

    code = "REVIEW_QUERY_INVALID"
    public_message = "The review query parameters are invalid."


class ReviewIngestionUnavailableError(ConflictError):
    """Review import was requested before a GBP location is connected and mapped."""

    code = "REVIEW_INGESTION_UNAVAILABLE"
    public_message = "Connect and map a Google Business Profile location before importing reviews."
