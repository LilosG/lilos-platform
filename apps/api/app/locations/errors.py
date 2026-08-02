"""Safe location-domain API errors."""

from apps.api.app.errors import ConflictError, NotFoundError


class LocationNotFoundError(NotFoundError):
    code = "LOCATION_NOT_FOUND"
    public_message = "The requested location was not found."


class LocationSlugConflictError(ConflictError):
    code = "LOCATION_SLUG_CONFLICT"
    public_message = "The location slug is already in use for this organization."


class LocationPrimaryConflictError(ConflictError):
    code = "LOCATION_PRIMARY_CONFLICT"
    public_message = "The organization already has a primary location."


class LocationVersionConflictError(ConflictError):
    code = "LOCATION_VERSION_CONFLICT"
    public_message = "The location changed after it was loaded."


class LocationTransitionConflictError(ConflictError):
    code = "LOCATION_TRANSITION_CONFLICT"
    public_message = "The location cannot perform that lifecycle transition."


class LocationParentStateConflictError(ConflictError):
    code = "LOCATION_PARENT_STATE_CONFLICT"
    public_message = "The organization state does not permit this location operation."
