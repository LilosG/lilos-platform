"""Stable access-domain errors without ownership or invitation disclosure."""

from http import HTTPStatus

from apps.api.app.errors import ApiError, ConflictError, NotFoundError
from apps.api.app.schemas import ErrorCategory


class MembershipNotFoundError(NotFoundError):
    code = "MEMBERSHIP_NOT_FOUND"
    public_message = "The requested membership was not found."


class MembershipConflictError(ConflictError):
    code = "MEMBERSHIP_CONFLICT"
    public_message = "The organization membership already exists."


class MembershipVersionConflictError(ConflictError):
    code = "MEMBERSHIP_VERSION_CONFLICT"
    public_message = "The membership changed before this operation completed."


class MembershipLifecycleConflictError(ConflictError):
    code = "MEMBERSHIP_LIFECYCLE_CONFLICT"
    public_message = "The requested membership transition is not permitted."


class AccessParentStateError(ConflictError):
    code = "ACCESS_PARENT_STATE_CONFLICT"
    public_message = "The parent state does not permit this access administration operation."


class InvitationNotFoundError(NotFoundError):
    code = "INVITATION_NOT_FOUND"
    public_message = "The requested invitation was not found."


class InvitationConflictError(ConflictError):
    code = "INVITATION_CONFLICT"
    public_message = "The invitation conflicts with an existing access record."


class InvitationVersionConflictError(ConflictError):
    code = "INVITATION_VERSION_CONFLICT"
    public_message = "The invitation changed before this operation completed."


class InvitationAcceptanceError(ConflictError):
    code = "INVITATION_ACCEPTANCE_FAILED"
    public_message = "The invitation could not be accepted."


class CatalogConflictError(ConflictError):
    code = "ACCESS_CATALOG_CONFLICT"
    public_message = "The access catalog does not match the approved catalog."


class AssignmentConflictError(ConflictError):
    code = "ROLE_ASSIGNMENT_CONFLICT"
    public_message = "The role assignment already exists or is not permitted."


class AssignmentNotFoundError(NotFoundError):
    code = "ROLE_ASSIGNMENT_NOT_FOUND"
    public_message = "The requested role assignment was not found."


class DenyConflictError(ConflictError):
    code = "PERMISSION_DENY_CONFLICT"
    public_message = "The permission deny already exists or is not permitted."


class DenyNotFoundError(NotFoundError):
    code = "PERMISSION_DENY_NOT_FOUND"
    public_message = "The requested permission deny was not found."


class ScopeValidationError(ApiError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    category = ErrorCategory.VALIDATION
    code = "ACCESS_SCOPE_INVALID"
    public_message = "The requested authorization scope is invalid."


class LastActiveOwnerConflictError(ConflictError):
    code = "LAST_ACTIVE_OWNER_CONFLICT"
    public_message = "The access change would violate organization continuity requirements."
