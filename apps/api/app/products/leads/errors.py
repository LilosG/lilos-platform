"""Safe Leads-domain errors exposed through the standard API envelope."""

from apps.api.app.errors import ConflictError, NotFoundError


class LeadSourceNotFoundError(NotFoundError):
    """An approved lead source identifier does not exist for this organization."""

    code = "LEAD_SOURCE_NOT_FOUND"
    public_message = "The requested lead source was not found."


class LeadNotFoundError(NotFoundError):
    """A lead identifier does not exist for this organization."""

    code = "LEAD_NOT_FOUND"
    public_message = "The requested lead was not found."


class LeadTaskNotFoundError(NotFoundError):
    """A lead task identifier does not exist for this lead."""

    code = "LEAD_TASK_NOT_FOUND"
    public_message = "The requested lead task was not found."


class LeadAssigneeNotFoundError(NotFoundError):
    """The requested user is not an active member of this organization."""

    code = "LEAD_ASSIGNEE_NOT_FOUND"
    public_message = "The requested lead assignee was not found."


class InvalidLeadTransitionError(ConflictError):
    """A lead status transition is not permitted from its current state."""

    code = "LEAD_INVALID_TRANSITION"
    public_message = "This status change is not permitted from the lead's current state."


class InvalidLeadQueryError(ConflictError):
    """A lead list query used an out-of-bounds pagination value."""

    code = "LEAD_QUERY_INVALID"
    public_message = "The lead query parameters are invalid."


class LeadSourceKeyConflictError(ConflictError):
    """A lead source key already exists for this organization."""

    code = "LEAD_SOURCE_KEY_CONFLICT"
    public_message = "A lead source with this key already exists for this organization."
