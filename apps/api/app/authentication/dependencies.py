"""Reusable bearer authentication dependency for future protected routes."""

import logging
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.authentication.contracts import AuthenticatedPrincipal, VerifiedProviderClaims
from apps.api.app.authentication.errors import (
    AuthenticationRequiredError,
    AuthenticationUnavailableError,
    TokenVerificationError,
    TokenVerificationUnavailableError,
)
from apps.api.app.authentication.service import AuthenticationService
from apps.api.app.authentication.verifier import SupabaseJwksVerifier, TokenVerifier
from apps.api.app.config import Settings
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id

logger = logging.getLogger("lilos.security.authentication")
service = AuthenticationService()


def verifier_from_request(request: Request) -> TokenVerifier:
    verifier = getattr(request.app.state, "authentication_verifier", None)
    if verifier is not None:
        return cast(TokenVerifier, verifier)
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise AuthenticationUnavailableError
    try:
        verifier = SupabaseJwksVerifier(settings)
    except ValueError:
        raise AuthenticationUnavailableError from None
    request.app.state.authentication_verifier = verifier
    return verifier


def bearer_token(request: Request) -> str:
    values = request.headers.getlist("authorization")
    if len(values) != 1:
        raise AuthenticationRequiredError
    scheme, separator, token = values[0].partition(" ")
    settings = request.app.state.settings
    max_bytes = settings.supabase_auth_max_token_bytes if isinstance(settings, Settings) else 16_384
    if (
        separator != " "
        or scheme.lower() != "bearer"
        or not token
        or token.strip() != token
        or any(character.isspace() for character in token)
        or len(token.encode("utf-8")) > max_bytes
    ):
        raise AuthenticationRequiredError
    return token


async def get_verified_provider_claims(request: Request) -> VerifiedProviderClaims:
    """Verify bearer transport and provider claims before opening a database transaction."""
    correlation_id = request_correlation_id(request)
    try:
        token = bearer_token(request)
        return await verifier_from_request(request).verify(token)
    except AuthenticationRequiredError:
        _security_log("rejected", "AUTHENTICATION_REQUIRED", correlation_id)
        raise
    except TokenVerificationError:
        _security_log("rejected", "TOKEN_REJECTED", correlation_id)
        raise AuthenticationRequiredError from None
    except TokenVerificationUnavailableError:
        _security_log("unavailable", "JWKS_UNAVAILABLE", correlation_id)
        raise AuthenticationUnavailableError from None


async def get_authenticated_principal(
    request: Request,
    claims: Annotated[VerifiedProviderClaims, Depends(get_verified_provider_claims)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> AuthenticatedPrincipal:
    correlation_id = request_correlation_id(request)
    try:
        principal = await service.authenticate(session, claims)
    except AuthenticationRequiredError:
        _security_log("rejected", "USER_NOT_ACTIVE", correlation_id)
        raise
    _security_log(
        "succeeded",
        "AUTHENTICATED",
        correlation_id,
        platform_user_id=str(principal.platform_user_id),
        assurance_level=principal.assurance_level.value,
    )
    return principal


def _security_log(
    result: str,
    reason_code: str,
    correlation_id: str,
    *,
    platform_user_id: str | None = None,
    assurance_level: str | None = None,
) -> None:
    logger.info(
        "Authentication evaluated",
        extra={
            "event_name": "security.authentication.evaluated",
            "correlation_id": correlation_id,
            "outcome": result,
            "normalized_error_code": reason_code,
            "platform_user_id": platform_user_id,
            "assurance_level": assurance_level,
        },
    )


Authenticated = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]
