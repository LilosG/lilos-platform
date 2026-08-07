"""Safe Content-domain errors exposed through the standard API envelope."""

from apps.api.app.errors import ConflictError, NotFoundError


class ContentOpportunityNotFoundError(NotFoundError):
    code = "CONTENT_OPPORTUNITY_NOT_FOUND"
    public_message = "The requested content opportunity was not found."


class ContentItemNotFoundError(NotFoundError):
    code = "CONTENT_ITEM_NOT_FOUND"
    public_message = "The requested content item was not found."


class ContentBriefNotFoundError(NotFoundError):
    code = "CONTENT_BRIEF_NOT_FOUND"
    public_message = "The requested content brief was not found."


class ContentRevisionNotFoundError(NotFoundError):
    code = "CONTENT_REVISION_NOT_FOUND"
    public_message = "The requested content revision was not found."


class ContentOpportunityNotDecidableError(ConflictError):
    code = "CONTENT_OPPORTUNITY_NOT_DECIDABLE"
    public_message = "This opportunity is not in a state that can be decided."


class ContentApprovalStageConflictError(ConflictError):
    code = "CONTENT_APPROVAL_STAGE_CONFLICT"
    public_message = "This revision is not eligible for the requested approval stage."


class ContentPublicationRequiresApprovedRevisionError(ConflictError):
    code = "CONTENT_PUBLICATION_REQUIRES_APPROVED_REVISION"
    public_message = "An approved revision and an active publishing target are required."


class ContentTargetNotConfiguredError(ConflictError):
    code = "CONTENT_TARGET_NOT_CONFIGURED"
    public_message = "No active, connected publishing target is configured."


class ContentGitHubProviderNotConfiguredError(ConflictError):
    code = "CONTENT_GITHUB_PROVIDER_NOT_CONFIGURED"
    public_message = (
        "The GitHub provider is not registered. Run the integration provider seed "
        "before configuring a GitHub publishing connection."
    )


class ContentPublicationNotAdvanceableError(ConflictError):
    code = "CONTENT_PUBLICATION_NOT_ADVANCEABLE"
    public_message = "This publication is not in a state that allows this transition."


class ContentQueryInvalidError(ConflictError):
    code = "CONTENT_QUERY_INVALID"
    public_message = "The content query parameters are invalid."
