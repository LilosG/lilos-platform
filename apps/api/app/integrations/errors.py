"""Safe integrations-domain errors exposed through the standard API envelope."""

from http import HTTPStatus

from apps.api.app.errors import ApiError, ConflictError, NotFoundError
from apps.api.app.schemas import ErrorCategory


class IntegrationNotConfiguredError(ApiError):
    """Google OAuth settings are not configured in this environment."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "INTEGRATION_NOT_CONFIGURED"
    category = ErrorCategory.SYSTEM
    retryable = False
    public_message = "This integration is not configured."


class IntegrationNotFoundError(NotFoundError):
    """No provider connection exists for this organization."""

    code = "INTEGRATION_CONNECTION_NOT_FOUND"
    public_message = "No provider connection was found for this organization."


class IntegrationStateInvalidError(ApiError):
    """The OAuth `state` parameter was missing, unknown, expired, or already used."""

    status_code = HTTPStatus.BAD_REQUEST
    code = "INTEGRATION_STATE_INVALID"
    category = ErrorCategory.VALIDATION
    public_message = "The authorization response could not be validated."


class IntegrationTokenExchangeFailedError(ApiError):
    """Google's token endpoint rejected the code/refresh-token exchange."""

    status_code = HTTPStatus.BAD_GATEWAY
    code = "INTEGRATION_TOKEN_EXCHANGE_FAILED"
    category = ErrorCategory.SYSTEM
    retryable = True
    public_message = "The provider rejected the token exchange."


class IntegrationReconnectRequiredError(ConflictError):
    """The stored refresh token is no longer valid; the user must reconnect."""

    code = "INTEGRATION_RECONNECT_REQUIRED"
    public_message = "This connection must be reconnected before it can be used."
