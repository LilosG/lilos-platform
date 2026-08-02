"""Temporary guarded authentication diagnostic route."""

from fastapi import APIRouter, Request, Response

from apps.api.app.authentication.contracts import (
    AuthenticatedPrincipalResponse,
)
from apps.api.app.authentication.dependencies import Authenticated
from apps.api.app.errors import request_correlation_id
from apps.api.app.schemas import ResponseMeta

router = APIRouter(prefix="/internal/auth", tags=["internal-authentication"])


@router.get(
    "/me",
    response_model=AuthenticatedPrincipalResponse,
    summary="Inspect the verified principal (temporary internal diagnostic route)",
)
async def current_principal(
    request: Request,
    response: Response,
    principal: Authenticated,
) -> AuthenticatedPrincipalResponse:
    response.headers["Cache-Control"] = "no-store"
    return AuthenticatedPrincipalResponse(
        data=principal,
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )
