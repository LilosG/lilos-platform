"""Google Business Profile OAuth connection routes.

Two distinct route shapes exist here, deliberately:

- Organization-scoped, authenticated, permission-checked JSON routes
  (`connect`, `status`, `disconnect`) follow the same pattern as every other
  product route in this codebase.
- The provider callback (`GET /api/v1/integrations/google/callback`) is fixed,
  unauthenticated, and organization-agnostic in its path, because it is the
  exact URL registered with Google and reached by a full browser navigation
  carrying no bearer token. Tenant identity is recovered entirely from the
  already-validated, hashed, one-time `state` parameter -- never from the URL.
"""

from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.administration.errors import (
    AdministrationNotFoundError,
    ReadinessBlockedError,
)
from apps.api.app.administration.service import AdministrationService
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.config import Settings
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.errors import (
    IntegrationNotConfiguredError,
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
    IntegrationStateInvalidError,
    IntegrationTokenExchangeFailedError,
)
from apps.api.app.products.gbp.discovery_service import GBPDiscoveryService
from apps.api.app.routes.health import settings_from_request
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/integrations/google",
    tags=["integrations"],
    dependencies=[Depends(get_authenticated_principal)],
)
callback_router = APIRouter(prefix="/api/v1/integrations/google", tags=["integrations"])
service = GBPConnectionService()
discovery = GBPDiscoveryService()
administration = AdministrationService()
Session = Annotated[AsyncSession, Depends(get_database_session)]
GBPConnect = Annotated[
    AuthorizationDecision,
    Depends(require_authorization("gbp.connect", ScopeType.ORGANIZATION, AssuranceLevel.AAL1)),
]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


NOT_EFFECTIVE_ENTITLEMENT_STATUSES = frozenset({"not_enabled", "archived", "suspended"})


async def _require_effective_entitlement(session: AsyncSession, organization_id: UUID) -> None:
    """Require an effective `gbp` entitlement before allowing a connection attempt.

    Deliberately narrower than the full product readiness engine
    (`AdministrationService.readiness`), which also evaluates business facts,
    configuration, approval policy, runtime controls, and onboarding -- none of
    which bear on whether an OAuth authorization can begin. This reuses the
    same entitlement-effectiveness rule `readiness()` applies
    (`ENTITLEMENT_NOT_EFFECTIVE`) without invoking those unrelated concerns.
    """
    product = await administration.catalog.get_product_by_key(session, "gbp")
    if product is None:
        raise AdministrationNotFoundError
    entitlement = await administration.entitlements.get_by_product(
        session, organization_id, product.id
    )
    if entitlement is None or entitlement.status in NOT_EFFECTIVE_ENTITLEMENT_STATUSES:
        raise ReadinessBlockedError


def _frontend_return_url(settings: Settings, *, connected: bool, reason: str | None = None) -> str:
    """Best-effort absolute redirect target for the browser after the callback.

    No dedicated frontend-base-URL setting exists; the exact environment
    contract for this feature is limited to the four Google/secret variables.
    The first configured `LILOS_WEB_ORIGINS` entry is reused as the frontend
    origin. If none is configured (only plausible in an incomplete local
    setup), this falls back to a same-origin relative path, which will not
    reach the real frontend -- a documented limitation, not a silent failure.
    """
    origins = settings.allowed_web_origins()
    base = origins[0] if origins else ""
    params = {"connected": "1"} if connected else {"connected": "0", "reason": reason or "error"}
    return f"{base}/gbp?{urlencode(params)}"


@router.post(
    "/connect",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(no_store)],
    summary="Begin a GBP OAuth connection",
)
async def connect(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: GBPConnect,
) -> dict[str, object]:
    await _require_effective_entitlement(session, organization_id)
    settings = settings_from_request(request)
    url = await service.begin_connection(
        session,
        settings,
        organization_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {"authorization_url": url},
        "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
    }


@router.get(
    "/status",
    dependencies=[Depends(no_store)],
    summary="Read the current GBP connection status",
)
async def connection_status(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: GBPConnect,
) -> dict[str, object]:
    connection = await service.find_connection(session, organization_id)
    data = (
        None
        if connection is None
        else {
            "status": connection.status,
            "token_expires_at": connection.token_expires_at,
            "last_verified_at": connection.last_verified_at,
        }
    )
    return {
        "data": data,
        "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
    }


@router.post(
    "/disconnect",
    dependencies=[Depends(no_store)],
    summary="Disconnect and revoke the current GBP connection",
)
async def disconnect(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: GBPConnect,
) -> dict[str, object]:
    settings = settings_from_request(request)
    connection = await service.disconnect(
        session,
        settings,
        organization_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {"status": connection.status},
        "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
    }


@router.post(
    "/discover",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(no_store)],
    summary="Discover GBP accounts, locations, and sync initial profiles",
)
async def discover(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: GBPConnect,
) -> dict[str, object]:
    settings = settings_from_request(request)
    try:
        result = await discovery.discover_and_sync(
            session,
            settings,
            organization_id,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except IntegrationReconnectRequiredError:
        return {
            "data": None,
            "error": {
                "code": "RECONNECT_REQUIRED",
                "message": "Google access token expired. Reconnect your Google account.",
            },
            "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
        }
    return {
        "data": result,
        "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
    }


@router.post(
    "/locations/{gbp_location_id}/sync",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(no_store)],
    summary="Sync the profile snapshot for a GBP location",
)
async def sync_profile(
    request: Request,
    organization_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    principal: Authenticated,
    _: GBPConnect,
) -> dict[str, object]:
    settings = settings_from_request(request)
    try:
        snapshot = await discovery.sync_profile(
            session,
            settings,
            organization_id,
            gbp_location_id,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except IntegrationReconnectRequiredError:
        return {
            "data": None,
            "error": {
                "code": "RECONNECT_REQUIRED",
                "message": "Google access token expired. Reconnect your Google account.",
            },
            "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
        }
    return {
        "data": {
            "snapshot_id": str(snapshot.id),
            "content_hash": snapshot.content_hash,
            "observed_at": snapshot.observed_at.isoformat(),
        },
        "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
    }


@callback_router.get(
    "/callback",
    include_in_schema=True,
    summary="Google OAuth redirect target (fixed, unauthenticated, organization-agnostic)",
)
async def callback(
    request: Request,
    session: Session,
    state: Annotated[str, Query(min_length=1, max_length=200)],
    code: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query(max_length=64)] = None,
) -> RedirectResponse:
    settings = settings_from_request(request)
    correlation_id = request_correlation_id(request)
    try:
        organization_id = await service.recover_organization_id(session, state)
    except IntegrationStateInvalidError:
        return RedirectResponse(
            url=_frontend_return_url(settings, connected=False, reason="invalid_state"),
            status_code=status.HTTP_302_FOUND,
        )
    if error or not code:
        await service.fail_connection(
            session,
            organization_id,
            state=state,
            provider_error=error or "missing_code",
            correlation_id=correlation_id,
        )
        return RedirectResponse(
            url=_frontend_return_url(settings, connected=False, reason=error or "missing_code"),
            status_code=status.HTTP_302_FOUND,
        )
    try:
        await service.complete_connection(
            session,
            settings,
            organization_id,
            state=state,
            code=code,
            correlation_id=correlation_id,
        )
    except (
        IntegrationStateInvalidError,
        IntegrationTokenExchangeFailedError,
        IntegrationNotFoundError,
        IntegrationNotConfiguredError,
    ) as exc:
        return RedirectResponse(
            url=_frontend_return_url(settings, connected=False, reason=type(exc).__name__.lower()),
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(
        url=_frontend_return_url(settings, connected=True),
        status_code=status.HTTP_302_FOUND,
    )
