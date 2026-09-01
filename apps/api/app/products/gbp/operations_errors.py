"""Safe GBP-operations errors exposed through the standard API envelope."""

from apps.api.app.errors import ConflictError, NotFoundError


class GBPLocationNotFoundError(NotFoundError):
    code = "GBP_LOCATION_NOT_FOUND"
    public_message = "The requested Business Profile location was not found."


class GBPLocationAlreadyMappedError(ConflictError):
    code = "GBP_LOCATION_ALREADY_MAPPED"
    public_message = (
        "This LILOs location already has a confirmed Business Profile mapping. "
        "Remove the existing mapping before mapping another profile."
    )


class GBPCapabilitySnapshotNotFoundError(NotFoundError):
    code = "GBP_CAPABILITY_SNAPSHOT_NOT_FOUND"
    public_message = "No capability snapshot has been recorded for this location yet."


class GBPCapabilityUnavailableError(ConflictError):
    code = "GBP_CAPABILITY_UNAVAILABLE"
    public_message = "This provider capability is not available for this location."


class GBPInvalidHoursError(ConflictError):
    code = "GBP_INVALID_HOURS"
    public_message = "The proposed hours are invalid or overlap."


class GBPChangeSetNotFoundError(NotFoundError):
    code = "GBP_CHANGE_SET_NOT_FOUND"
    public_message = "The requested change set was not found."


class GBPChangeSetNotDecidableError(ConflictError):
    code = "GBP_CHANGE_SET_NOT_DECIDABLE"
    public_message = "This change set is not in a state that can be decided."


class GBPSpecialHoursNotFoundError(NotFoundError):
    code = "GBP_SPECIAL_HOURS_NOT_FOUND"
    public_message = "The requested special hours revision was not found."


class GBPMediaNotFoundError(NotFoundError):
    code = "GBP_MEDIA_NOT_FOUND"
    public_message = "The requested media item was not found."


class GBPPostRevisionNotFoundError(NotFoundError):
    code = "GBP_POST_REVISION_NOT_FOUND"
    public_message = "The requested post revision was not found."


class GBPPostNotPublishEligibleError(ConflictError):
    code = "GBP_POST_NOT_PUBLISH_ELIGIBLE"
    public_message = "An approved post revision on a write-enabled location is required."


class GBPPostPublicationExistsError(ConflictError):
    code = "GBP_POST_PUBLICATION_EXISTS"
    public_message = "This approved post revision already has a publication record."


class GBPSuspensionCaseNotFoundError(NotFoundError):
    code = "GBP_SUSPENSION_CASE_NOT_FOUND"
    public_message = "The requested suspension case was not found."


class GBPLocationNotWriteEnabledError(ConflictError):
    code = "GBP_LOCATION_NOT_WRITE_ENABLED"
    public_message = "This location is not confirmed and write-enabled."


class GBPMediaNotPublishEligibleError(ConflictError):
    code = "GBP_MEDIA_NOT_PUBLISH_ELIGIBLE"
    public_message = "An approved media item on a write-enabled location is required."
