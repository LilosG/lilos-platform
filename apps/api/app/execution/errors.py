"""Safe workflow-execution errors exposed through the standard API envelope."""

from apps.api.app.errors import AuthorizationError, ConflictError, NotFoundError


class WorkflowKeyUnknownError(NotFoundError):
    """The requested workflow type key is not a registered workflow."""

    code = "WORKFLOW_KEY_UNKNOWN"
    public_message = "The requested workflow type was not found."


class WorkflowLocationScopeError(NotFoundError):
    """The requested location does not belong to this organization."""

    code = "WORKFLOW_LOCATION_NOT_FOUND"
    public_message = "The requested location was not found for this organization."


class WorkflowIdempotencyConflictError(ConflictError):
    """The same idempotency key was reused with a different request payload."""

    code = "WORKFLOW_IDEMPOTENCY_CONFLICT"
    public_message = "This idempotency key was already used with a different request."


class WorkflowRunNotFoundError(NotFoundError):
    """The referenced workflow run does not exist for this organization."""

    code = "WORKFLOW_RUN_NOT_FOUND"
    public_message = "The referenced workflow run was not found."


class WorkflowRunTypeMismatchError(ConflictError):
    """The referenced workflow run was not started for the expected workflow type."""

    code = "WORKFLOW_RUN_TYPE_MISMATCH"
    public_message = "The referenced workflow run does not match the expected workflow type."


class WorkflowRunNotAvailableError(ConflictError):
    """The referenced workflow run is not in a state that can be consumed."""

    code = "WORKFLOW_RUN_NOT_AVAILABLE"
    public_message = (
        "The referenced workflow run has already been used, completed, or is otherwise unavailable."
    )


class AutomationRunNotAllowedError(AuthorizationError):
    """Only read-only sync, ingest and crawl automations can be run on demand."""

    code = "AUTOMATION_RUN_NOT_ALLOWED"
    public_message = "This automation cannot be run on demand."


class AutomationPausedError(ConflictError):
    """A paused automation is not run until it is resumed."""

    code = "AUTOMATION_PAUSED"
    public_message = "This automation is paused."


class AutomationRunInProgressError(ConflictError):
    """The schedule already has a queued or running run."""

    code = "AUTOMATION_RUN_IN_PROGRESS"
    public_message = "This automation is already running."


class AutomationLocationRetiredError(ConflictError):
    """The automation belongs to a location that is archived or closed for good."""

    code = "AUTOMATION_LOCATION_RETIRED"
    public_message = "This automation belongs to a location that is no longer in use."
