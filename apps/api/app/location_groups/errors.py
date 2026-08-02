"""Stable location-group domain errors."""

from apps.api.app.errors import ConflictError, NotFoundError


class LocationGroupNotFoundError(NotFoundError):
    code = "LOCATION_GROUP_NOT_FOUND"
    public_message = "The requested location group was not found."


class LocationGroupKeyConflictError(ConflictError):
    code = "LOCATION_GROUP_KEY_CONFLICT"
    public_message = "The location-group key is already in use."


class LocationGroupVersionConflictError(ConflictError):
    code = "LOCATION_GROUP_VERSION_CONFLICT"
    public_message = "The location group changed after it was loaded."


class LocationGroupStateConflictError(ConflictError):
    code = "LOCATION_GROUP_STATE_CONFLICT"
    public_message = "The location group state does not permit that operation."


class LocationGroupParentStateConflictError(ConflictError):
    code = "LOCATION_GROUP_PARENT_STATE_CONFLICT"
    public_message = "The parent organization state does not permit that operation."


class LocationGroupLocationStateConflictError(ConflictError):
    code = "LOCATION_GROUP_LOCATION_STATE_CONFLICT"
    public_message = "The location state does not permit a new group membership."


class LocationGroupMembershipConflictError(ConflictError):
    code = "LOCATION_GROUP_MEMBERSHIP_CONFLICT"
    public_message = "The location is already a member of this group."


class LocationGroupMembershipNotFoundError(NotFoundError):
    code = "LOCATION_GROUP_MEMBERSHIP_NOT_FOUND"
    public_message = "The requested location-group membership was not found."
