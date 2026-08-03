"""Non-disclosing authorization failure contract."""

from apps.api.app.errors import AuthorizationError


class AuthorizationDeniedError(AuthorizationError):
    code = "AUTHORIZATION_DENIED"
    public_message = "Authorization is required for this action."
    response_headers = {"Cache-Control": "no-store"}
