"""Safe authentication and platform-user errors."""

from http import HTTPStatus

from apps.api.app.errors import ApiError, ConflictError, NotFoundError
from apps.api.app.schemas import ErrorCategory


class AuthenticationRequiredError(ApiError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "AUTHENTICATION_REQUIRED"
    category = ErrorCategory.AUTHENTICATION
    public_message = "Authentication is required."
    response_headers = {"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"}


class AuthenticationUnavailableError(ApiError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "AUTHENTICATION_UNAVAILABLE"
    category = ErrorCategory.SYSTEM
    public_message = "Authentication is temporarily unavailable."
    retryable = True
    response_headers = {"Cache-Control": "no-store"}


class UserProfileNotFoundError(NotFoundError):
    code = "USER_PROFILE_NOT_FOUND"
    public_message = "The requested user profile was not found."


class UserProfileConflictError(ConflictError):
    code = "USER_PROFILE_CONFLICT"
    public_message = "The user profile mapping already exists."


class UserVersionConflictError(ConflictError):
    code = "USER_VERSION_CONFLICT"
    public_message = "The user profile changed before this operation completed."


class UserLifecycleConflictError(ConflictError):
    code = "USER_LIFECYCLE_CONFLICT"
    public_message = "The requested user lifecycle transition is not permitted."


class TokenVerificationError(Exception):
    """Internal generic token rejection; never returned with its detail."""


class TokenVerificationUnavailableError(Exception):
    """Internal provider/JWKS availability failure."""
