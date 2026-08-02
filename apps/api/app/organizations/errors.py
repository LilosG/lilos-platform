"""Safe organization-domain errors exposed through the standard API envelope."""

from apps.api.app.errors import ConflictError, NotFoundError


class OrganizationNotFoundError(NotFoundError):
    """An organization identifier does not exist."""

    code = "ORGANIZATION_NOT_FOUND"
    public_message = "The requested organization was not found."


class OrganizationSlugConflictError(ConflictError):
    """An immutable organization slug is already reserved."""

    code = "ORGANIZATION_SLUG_CONFLICT"
    public_message = "The organization slug is already in use."


class OrganizationVersionConflictError(ConflictError):
    """A lifecycle request used a stale optimistic-concurrency version."""

    code = "ORGANIZATION_VERSION_CONFLICT"
    public_message = "The organization changed after it was loaded."


class OrganizationTransitionConflictError(ConflictError):
    """The requested lifecycle action is invalid from the current state."""

    code = "ORGANIZATION_TRANSITION_CONFLICT"
    public_message = "The organization cannot perform that lifecycle transition."
