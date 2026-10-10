"""Website publishing setup for the Command Center Integrations screen.

A GitHub authorization and a Content publishing destination are distinct records. This module
reads which of the two exist for a client, lists the repositories the client's GitHub installation
can reach, and links one of them as the client's publishing target. Linking is refused for any
repository whose blog format has not been verified, so nothing publishes against an unchecked
format. Every state and error is a code; the console writes the words.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.domains.enums import OrganizationDomainStatus
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.errors import ApiError, ConflictError, NotFoundError, request_correlation_id
from apps.api.app.execution.models import IdempotencyRecord
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.contracts import TargetCreate
from apps.api.app.products.content.errors import ContentTargetNotConfiguredError
from apps.api.app.products.content.github_app_service import (
    DiscoveredRepository,
    GitHubAppService,
    installation_id_from_reference,
)
from apps.api.app.products.content.models import PublishingTarget
from apps.api.app.products.content.publishing_target_reconciliation import (
    select_repository_for_client,
)
from apps.api.app.products.content.service import ContentService
from apps.api.app.products.content.target_contract_catalog import CONTRACTS
from apps.api.app.routes.health import settings_from_request
from apps.api.app.routes.seo import Session, no_store, policy
from apps.api.app.schemas import ErrorCategory

IDEMPOTENCY_NAMESPACE = "publishing.target.create"
IDEMPOTENCY_TTL = timedelta(hours=24)
PRIMARY_TARGET_KEY = "primary-site"
BLOG_PATH_PREFIX = "src/content/blog"

github = GitHubAppService()
content = ContentService()

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center/integrations/publishing",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(no_store)],
)


class PublishingSetupState(StrEnum):
    LINKED = "linked"
    NOT_LINKED = "not_linked"
    GITHUB_NOT_CONNECTED = "github_not_connected"
    FORMAT_UNVERIFIED = "format_unverified"


class PublishingSetup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    state: PublishingSetupState
    repository: str | None
    branch: str | None
    can_manage: bool


class PublishingRepository(BaseModel):
    model_config = ConfigDict(extra="ignore")
    repository_id: str
    name: str
    default_branch: str
    private: bool
    format_verified: bool
    suggested: bool


class PublishingRepositories(BaseModel):
    model_config = ConfigDict(extra="ignore")
    repositories: list[PublishingRepository]


class LinkPublishingTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: str = Field(min_length=1, max_length=255)


class LinkedPublishingTarget(BaseModel):
    model_config = ConfigDict(extra="ignore")
    repository: str
    branch: str
    replayed: bool


class PublishingGitHubNotConnectedError(ConflictError):
    code = "PUBLISHING_GITHUB_NOT_CONNECTED"
    public_message = "GitHub is not connected for this client."


class PublishingRepositoriesUnavailableError(ApiError):
    status_code = HTTPStatus.BAD_GATEWAY
    code = "PUBLISHING_REPOSITORIES_UNAVAILABLE"
    category = ErrorCategory.SYSTEM
    retryable = True
    public_message = "The repositories could not be loaded from GitHub."


class PublishingRepositoryNotAccessibleError(NotFoundError):
    code = "PUBLISHING_REPOSITORY_NOT_ACCESSIBLE"
    public_message = "That repository is not available to this client."


class PublishingFormatUnverifiedError(ConflictError):
    code = "PUBLISHING_FORMAT_UNVERIFIED"
    public_message = "The blog format of this repository has not been checked yet."


class PublishingTargetExistsError(ConflictError):
    code = "PUBLISHING_TARGET_EXISTS"
    public_message = "This client already has a publishing repository."


class PublishingIdempotencyConflictError(ConflictError):
    code = "PUBLISHING_IDEMPOTENCY_CONFLICT"
    public_message = "This request key was already used for a different repository."


async def active_targets(session: AsyncSession, organization_id: UUID) -> list[PublishingTarget]:
    return [
        target
        for target in await content.list_targets(session, organization_id)
        if target.status == "active"
    ]


async def read_publishing_setup(
    session: AsyncSession, organization_id: UUID, *, can_manage: bool
) -> PublishingSetup:
    """Where this client's website publishing stands. No provider I/O."""
    targets = await active_targets(session, organization_id)
    if targets:
        target = targets[0]
        return PublishingSetup(
            state=PublishingSetupState.LINKED
            if target.frontmatter_contract
            else PublishingSetupState.FORMAT_UNVERIFIED,
            repository=target.repository_id,
            branch=target.base_branch,
            can_manage=can_manage,
        )
    connection = await github.find_connection(session, organization_id)
    connected = (
        connection is not None
        and connection.status == "connected"
        and installation_id_from_reference(connection.external_account_reference) is not None
    )
    return PublishingSetup(
        state=PublishingSetupState.NOT_LINKED
        if connected
        else PublishingSetupState.GITHUB_NOT_CONNECTED,
        repository=None,
        branch=None,
        can_manage=can_manage,
    )


async def accessible_repositories(
    request: Request, session: AsyncSession, organization_id: UUID
) -> tuple[UUID, list[DiscoveredRepository]]:
    """The connection id and repositories this client's own installation can reach."""
    connection = await github.find_connection(session, organization_id)
    installation_id = (
        installation_id_from_reference(connection.external_account_reference)
        if connection is not None and connection.status == "connected"
        else None
    )
    if connection is None or installation_id is None:
        raise PublishingGitHubNotConnectedError
    try:
        repositories = await github.list_installation_repositories(
            settings_from_request(request), installation_id
        )
    except Exception as error:
        raise PublishingRepositoriesUnavailableError from error
    return connection.id, repositories


async def suggested_repository(
    session: AsyncSession, organization_id: UUID, repositories: list[DiscoveredRepository]
) -> str | None:
    organization = await session.get(Organization, organization_id)
    primary_domain = await session.scalar(
        select(OrganizationDomain).where(
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.is_primary.is_(True),
            OrganizationDomain.status == OrganizationDomainStatus.ACTIVE,
        )
    )
    chosen = select_repository_for_client(
        repositories,
        primary_domain=primary_domain.domain if primary_domain else None,
        website_url=organization.website_url if organization else None,
        organization_slug=organization.slug if organization else None,
    )
    return chosen.repository_id if chosen else None


@router.get("/repositories", response_model=PublishingRepositories)
async def publishing_repositories(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[object, policy("content.manage_targets", aal2=True)],
) -> PublishingRepositories:
    _connection_id, repositories = await accessible_repositories(request, session, organization_id)
    suggested = await suggested_repository(session, organization_id, repositories)
    return PublishingRepositories(
        repositories=[
            PublishingRepository(
                repository_id=repository.repository_id,
                name=repository.name,
                default_branch=repository.default_branch,
                private=repository.private,
                format_verified=repository.repository_id in CONTRACTS,
                suggested=repository.repository_id == suggested,
            )
            for repository in repositories
        ]
    )


@router.post("/target", response_model=LinkedPublishingTarget)
async def link_publishing_target(
    request: Request,
    response: Response,
    organization_id: UUID,
    body: LinkPublishingTarget,
    session: Session,
    principal: Authenticated,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
    _: Annotated[object, policy("content.manage_targets", aal2=True)],
) -> LinkedPublishingTarget:
    """Link the client's publishing repository. One key creates one target, however often sent."""
    request_hash = sha256(body.repository_id.encode()).hexdigest()
    record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.organization_id == organization_id,
            IdempotencyRecord.namespace == IDEMPOTENCY_NAMESPACE,
            IdempotencyRecord.key == idempotency_key,
        )
    )
    if record is not None:
        if record.request_hash != request_hash:
            raise PublishingIdempotencyConflictError
        existing = (
            await session.scalar(
                select(PublishingTarget).where(
                    PublishingTarget.organization_id == organization_id,
                    PublishingTarget.id == record.resource_id,
                )
            )
            if record.resource_id
            else None
        )
        if existing is not None:
            return LinkedPublishingTarget(
                repository=existing.repository_id, branch=existing.base_branch, replayed=True
            )

    connection_id, repositories = await accessible_repositories(request, session, organization_id)
    repository = next(
        (item for item in repositories if item.repository_id == body.repository_id), None
    )
    if repository is None:
        raise PublishingRepositoryNotAccessibleError
    if repository.repository_id not in CONTRACTS:
        raise PublishingFormatUnverifiedError
    if await active_targets(session, organization_id):
        raise PublishingTargetExistsError
    try:
        target = await content.create_target(
            session,
            organization_id,
            TargetCreate(
                key=PRIMARY_TARGET_KEY,
                connection_id=connection_id,
                repository_id=repository.repository_id,
                base_branch=repository.default_branch or "main",
                allowed_path_prefix=BLOG_PATH_PREFIX,
            ),
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except ContentTargetNotConfiguredError as error:
        raise PublishingGitHubNotConnectedError from error
    session.add(
        IdempotencyRecord(
            organization_id=organization_id,
            namespace=IDEMPOTENCY_NAMESPACE,
            key=idempotency_key,
            request_hash=request_hash,
            status="completed",
            resource_id=target.id,
            expires_at=datetime.now(UTC) + IDEMPOTENCY_TTL,
        )
    )
    await session.flush()
    response.status_code = status.HTTP_201_CREATED
    return LinkedPublishingTarget(
        repository=target.repository_id, branch=target.base_branch, replayed=False
    )
