"""GitHub App installation and repository discovery routes.

Normal production content publishing uses a GitHub App installation (not a
PAT). These routes drive the install flow, callback, and repository discovery.
The PAT fallback remains on the content product routes for advanced use.
"""

from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.config import Settings
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.integrations.errors import (
    IntegrationNotConfiguredError,
    IntegrationNotFoundError,
    IntegrationStateInvalidError,
)
from apps.api.app.products.content.github_app_service import (
    GitHubAppService,
    installation_id_from_reference,
)
from apps.api.app.routes.health import settings_from_request
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/integrations/github",
    tags=["integrations"],
    dependencies=[Depends(get_authenticated_principal)],
)
callback_router = APIRouter(prefix="/api/v1/integrations/github", tags=["integrations"])
service = GitHubAppService()
Session = Annotated[AsyncSession, Depends(get_database_session)]
GitHubManage = Annotated[
    AuthorizationDecision,
    Depends(
        require_authorization("content.manage_targets", ScopeType.ORGANIZATION, AssuranceLevel.AAL2)
    ),
]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _frontend_return_url(settings: Settings, *, installed: bool, reason: str | None = None) -> str:
    origins = settings.allowed_web_origins()
    base = origins[0] if origins else ""
    params = {"installed": "1"} if installed else {"installed": "0", "reason": reason or "error"}
    return f"{base}/integrations?{urlencode(params)}"


@router.post(
    "/install",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(no_store)],
    summary="Begin the GitHub App installation flow",
)
async def begin_install(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: GitHubManage,
) -> dict[str, object]:
    settings = settings_from_request(request)
    url = await service.begin_install(
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
    "/repositories",
    dependencies=[Depends(no_store)],
    summary="List repositories accessible to the installation",
)
async def list_repositories(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: GitHubManage,
) -> dict[str, object]:
    settings = settings_from_request(request)
    connection = await service.find_connection(session, organization_id)
    if connection is None:
        return {
            "data": [],
            "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
        }
    installation_id = installation_id_from_reference(connection.external_account_reference)
    if installation_id is None:
        return {
            "data": [],
            "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
        }
    try:
        repos = await service.list_installation_repositories(settings, installation_id)
    except Exception as exc:
        del exc
        return {
            "data": [],
            "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
        }
    return {
        "data": [
            {
                "repository_id": r.repository_id,
                "name": r.name,
                "default_branch": r.default_branch,
                "private": r.private,
            }
            for r in repos
        ],
        "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
    }


@router.post(
    "/disconnect",
    dependencies=[Depends(no_store)],
    summary="Disconnect the local GitHub App installation binding",
)
async def disconnect_installation(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: GitHubManage,
) -> dict[str, object]:
    item = await service.disconnect_installation(
        session,
        organization_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {"status": item.status},
        "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
    }


@callback_router.get(
    "/callback",
    include_in_schema=True,
    summary="GitHub App installation redirect target (fixed, unauthenticated)",
)
async def github_callback(
    request: Request,
    session: Session,
    state: Annotated[str, Query(min_length=1, max_length=200)],
    installation_id: Annotated[str | None, Query()] = None,
    setup_action: Annotated[str | None, Query(max_length=64)] = None,
    error: Annotated[str | None, Query(max_length=64)] = None,
) -> RedirectResponse:
    settings = settings_from_request(request)
    correlation_id = request_correlation_id(request)
    try:
        organization_id = await service.recover_organization_id(session, state)
    except IntegrationStateInvalidError:
        return RedirectResponse(
            url=_frontend_return_url(settings, installed=False, reason="invalid_state"),
            status_code=status.HTTP_302_FOUND,
        )
    if error or not installation_id:
        await service.fail_install(
            session,
            organization_id,
            state=state,
            provider_error=error or "missing_installation_id",
            correlation_id=correlation_id,
        )
        return RedirectResponse(
            url=_frontend_return_url(
                settings, installed=False, reason=error or "missing_installation_id"
            ),
            status_code=status.HTTP_302_FOUND,
        )
    try:
        await service.complete_install(
            session,
            settings,
            organization_id,
            state=state,
            installation_id=installation_id,
            setup_action=setup_action,
            correlation_id=correlation_id,
        )
    except (IntegrationStateInvalidError, IntegrationNotFoundError, IntegrationNotConfiguredError):
        return RedirectResponse(
            url=_frontend_return_url(settings, installed=False, reason="install_failed"),
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(
        url=_frontend_return_url(settings, installed=True),
        status_code=status.HTTP_302_FOUND,
    )
