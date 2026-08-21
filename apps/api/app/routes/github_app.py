"""GitHub App installation and repository discovery routes.

Normal production content publishing uses a GitHub App installation (not a
PAT). These routes drive the install flow, callback, repository discovery, and
idempotent publishing-target reconciliation for single-repository clients.
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
from apps.api.app.integrations.directory_service import IntegrationDirectoryService
from apps.api.app.integrations.errors import (
    IntegrationNotConfiguredError,
    IntegrationNotFoundError,
    IntegrationStateInvalidError,
)
from apps.api.app.products.content.contracts import TargetCreate
from apps.api.app.products.content.github_app_service import (
    DiscoveredRepository,
    GitHubAppService,
    installation_id_from_reference,
)
from apps.api.app.products.content.service import ContentService
from apps.api.app.routes.health import settings_from_request
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/integrations/github",
    tags=["integrations"],
    dependencies=[Depends(get_authenticated_principal)],
)
callback_router = APIRouter(prefix="/api/v1/integrations/github", tags=["integrations"])
service = GitHubAppService()
directory_service = IntegrationDirectoryService()
content_service = ContentService()
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


async def _ensure_default_publishing_target(
    session: AsyncSession,
    organization_id: UUID,
    connection_id: UUID,
    repositories: list[DiscoveredRepository],
    *,
    actor_id: UUID | None,
    correlation_id: str,
) -> None:
    """Create the conventional Astro publishing target when selection is unambiguous.

    A GitHub App installation can expose many repositories. LILOs only auto-
    reconciles a target when exactly one repository is authorized and the
    organization has no publishing target yet. Multi-repository installations
    remain explicit so the platform never guesses a client destination.
    """
    existing = await content_service.list_targets(session, organization_id)
    if existing or len(repositories) != 1:
        return
    repository = repositories[0]
    await content_service.create_target(
        session,
        organization_id,
        TargetCreate(
            key="primary-site",
            connection_id=connection_id,
            target_type="github_astro",
            repository_id=repository.repository_id,
            base_branch=repository.default_branch or "main",
            allowed_path_prefix="src/content/blog",
            deployment_target_reference=None,
        ),
        actor_id=actor_id,
        correlation_id=correlation_id,
    )


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
    except Exception:
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
        connection = await service.complete_install(
            session,
            settings,
            organization_id,
            state=state,
            installation_id=installation_id,
            setup_action=setup_action,
            correlation_id=correlation_id,
        )
        repositories = await service.list_installation_repositories(settings, installation_id)
        await _ensure_default_publishing_target(
            session,
            organization_id,
            connection.id,
            repositories,
            actor_id=None,
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


@router.get(
    "/workspace",
    dependencies=[Depends(no_store)],
    summary="GitHub provider detail workspace",
)
async def github_workspace(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _authz: GitHubManage,
) -> dict[str, object]:
    """GitHub detail: installation state, accessible repositories, target reconciliation."""
    settings = settings_from_request(request)
    ws = await directory_service.github_workspace(session, organization_id)

    repositories: list[dict[str, object]] = []
    discovered: list[DiscoveredRepository] = []
    if ws.connection_id is not None and ws.external_account_reference is not None:
        installation_id = installation_id_from_reference(ws.external_account_reference)
        if installation_id is not None:
            try:
                discovered = await service.list_installation_repositories(settings, installation_id)
                repositories = [
                    {
                        "repository_id": r.repository_id,
                        "name": r.name,
                        "default_branch": r.default_branch,
                        "private": r.private,
                    }
                    for r in discovered
                ]
                await _ensure_default_publishing_target(
                    session,
                    organization_id,
                    UUID(ws.connection_id),
                    discovered,
                    actor_id=principal.platform_user_id,
                    correlation_id=request_correlation_id(request),
                )
            except Exception:
                repositories = []

    targets = await content_service.list_targets(session, organization_id)
    return {
        "data": {
            "connection_status": ws.connection_status,
            "connection_id": ws.connection_id,
            "external_account_reference": ws.external_account_reference,
            "repositories": repositories,
            "publishing_targets": [
                {
                    "id": str(target.id),
                    "key": target.key,
                    "repository_id": target.repository_id,
                    "base_branch": target.base_branch,
                    "allowed_path_prefix": target.allowed_path_prefix,
                    "status": target.status,
                }
                for target in targets
            ],
        },
        "meta": ResponseMeta(correlation_id=request_correlation_id(request)).model_dump(),
    }
