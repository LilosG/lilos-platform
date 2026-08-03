"""Guarded protected routes proving fixed server-side authorization policies."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import (
    AuthorizationDecision,
    AuthorizedResponse,
    AuthorizedResult,
)
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.errors import request_correlation_id
from apps.api.app.schemas import ResponseMeta

router = APIRouter(tags=["internal-authorization-test"])


def authorized_response(request: Request, response: Response) -> AuthorizedResponse:
    response.headers["Cache-Control"] = "no-store"
    return AuthorizedResponse(
        data=AuthorizedResult(),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


OrganizationRead = Annotated[
    AuthorizationDecision,
    Depends(require_authorization("organization.read", ScopeType.ORGANIZATION)),
]
LocationRead = Annotated[
    AuthorizationDecision,
    Depends(require_authorization("locations.read", ScopeType.LOCATION)),
]
OrganizationUpdate = Annotated[
    AuthorizationDecision,
    Depends(require_authorization("organization.update", ScopeType.ORGANIZATION)),
]
LocationUpdate = Annotated[
    AuthorizationDecision,
    Depends(require_authorization("locations.update", ScopeType.LOCATION)),
]
OrganizationAal2 = Annotated[
    AuthorizationDecision,
    Depends(
        require_authorization(
            "organization.settings.manage", ScopeType.ORGANIZATION, AssuranceLevel.AAL2
        )
    ),
]


@router.get(
    "/internal/organizations/{organization_id}/authorization-test/organization-read",
    response_model=AuthorizedResponse,
)
async def organization_read(
    request: Request,
    response: Response,
    organization_id: UUID,
    decision: OrganizationRead,
) -> AuthorizedResponse:
    del organization_id, decision
    return authorized_response(request, response)


@router.get(
    "/internal/organizations/{organization_id}/authorization-test/location-read/{location_id}",
    response_model=AuthorizedResponse,
)
async def location_read(
    request: Request,
    response: Response,
    organization_id: UUID,
    location_id: UUID,
    decision: LocationRead,
) -> AuthorizedResponse:
    del organization_id, location_id, decision
    return authorized_response(request, response)


@router.post(
    "/internal/organizations/{organization_id}/authorization-test/organization-update",
    response_model=AuthorizedResponse,
)
async def organization_update(
    request: Request,
    response: Response,
    organization_id: UUID,
    decision: OrganizationUpdate,
) -> AuthorizedResponse:
    del organization_id, decision
    return authorized_response(request, response)


@router.post(
    "/internal/organizations/{organization_id}/authorization-test/location-update/{location_id}",
    response_model=AuthorizedResponse,
)
async def location_update(
    request: Request,
    response: Response,
    organization_id: UUID,
    location_id: UUID,
    decision: LocationUpdate,
) -> AuthorizedResponse:
    del organization_id, location_id, decision
    return authorized_response(request, response)


@router.post(
    "/internal/organizations/{organization_id}/authorization-test/aal2",
    response_model=AuthorizedResponse,
)
async def aal2(
    request: Request,
    response: Response,
    organization_id: UUID,
    decision: OrganizationAal2,
) -> AuthorizedResponse:
    del organization_id, decision
    return authorized_response(request, response)
