"""Stable profile-domain errors."""

from apps.api.app.errors import ConflictError, NotFoundError


class OrganizationProfileNotFoundError(NotFoundError):
    code = "ORGANIZATION_PROFILE_NOT_FOUND"
    public_message = "The requested organization profile was not found."


class OrganizationProfileConflictError(ConflictError):
    code = "ORGANIZATION_PROFILE_CONFLICT"
    public_message = "The organization already has a profile."


class OrganizationProfileVersionConflictError(ConflictError):
    code = "ORGANIZATION_PROFILE_VERSION_CONFLICT"
    public_message = "The organization profile changed after it was loaded."


class LocationProfileNotFoundError(NotFoundError):
    code = "LOCATION_PROFILE_NOT_FOUND"
    public_message = "The requested location profile was not found."


class LocationProfileConflictError(ConflictError):
    code = "LOCATION_PROFILE_CONFLICT"
    public_message = "The location already has a profile."


class LocationProfileVersionConflictError(ConflictError):
    code = "LOCATION_PROFILE_VERSION_CONFLICT"
    public_message = "The location profile changed after it was loaded."


class ProfileParentStateConflictError(ConflictError):
    code = "PROFILE_PARENT_STATE_CONFLICT"
    public_message = "The parent lifecycle state does not permit profile mutation."
