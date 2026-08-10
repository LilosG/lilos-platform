"""Protected governed Content APIs."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.content.contracts import (
    AIDraftCreate,
    ApprovalDecision,
    BriefCreate,
    GitHubConnectionCreate,
    ItemCreate,
    OpportunityCreate,
    OpportunityDecision,
    PublicationCreate,
    RevisionCreate,
    TargetCreate,
)
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)
from apps.api.app.products.content.service import ContentService
from apps.api.app.routes.health import settings_from_request

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/content",
    tags=["content"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = ContentService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def policy(key: str, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            key, ScopeType.ORGANIZATION, AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1
        )
    )


def meta(request: Request) -> dict[str, object]:
    return {"correlation_id": request_correlation_id(request)}


def opportunity_row(item: ContentOpportunity) -> dict[str, object]:
    return {
        "id": str(item.id),
        "location_id": str(item.location_id) if item.location_id else None,
        "product_key": item.product_key,
        "target_reference": item.target_reference,
        "opportunity_type": item.opportunity_type,
        "priority_score": item.priority_score,
        "status": item.status,
    }


def item_row(item: ContentItem) -> dict[str, object]:
    return {
        "id": str(item.id),
        "opportunity_id": str(item.opportunity_id) if item.opportunity_id else None,
        "location_id": str(item.location_id) if item.location_id else None,
        "content_type": item.content_type,
        "title": item.title,
        "slug": item.slug,
        "status": item.status,
        "published_at": item.published_at,
    }


def brief_row(item: ContentBrief) -> dict[str, object]:
    return {
        "id": str(item.id),
        "revision_number": item.revision_number,
        "audience": item.audience,
        "intent": item.intent,
        "target_reference": item.target_reference,
        "approved_fact_revision_ids": item.approved_fact_revision_ids,
        "status": item.status,
    }


def revision_row(item: ContentRevision) -> dict[str, object]:
    return {
        "id": str(item.id),
        "revision_number": item.revision_number,
        "body": item.body,
        "frontmatter": item.frontmatter,
        "created_by_type": item.created_by_type,
        "status": item.status,
        "validation_document": item.validation_document,
        "approved_at": item.approved_at,
    }


def publication_row(item: ContentPublication) -> dict[str, object]:
    return {
        "id": str(item.id),
        "status": item.status,
        "target_path": item.target_path,
        "branch_name": item.branch_name,
        "external_pull_request_id": item.external_pull_request_id,
        "build_status": item.build_status,
        "deployment_status": item.deployment_status,
        "published_url": item.published_url,
        "verified_at": item.verified_at,
    }


def target_row(item: PublishingTarget) -> dict[str, object]:
    return {
        "id": str(item.id),
        "key": item.key,
        "target_type": item.target_type,
        "repository_id": item.repository_id,
        "base_branch": item.base_branch,
        "allowed_path_prefix": item.allowed_path_prefix,
        "status": item.status,
    }


@router.get("/targets", dependencies=[Depends(no_store)])
async def list_targets(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
) -> dict[str, object]:
    items = await service.list_targets(session, organization_id)
    return {"data": [target_row(item) for item in items], "meta": meta(request)}


def connection_row(item: IntegrationConnection) -> dict[str, object]:
    return {
        "id": str(item.id),
        "external_account_reference": item.external_account_reference,
        "status": item.status,
    }


@router.get("/connections", dependencies=[Depends(no_store)])
async def list_connections(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
) -> dict[str, object]:
    """List GitHub integration connections available for publishing targets."""
    items = await service.list_github_connections(session, organization_id)
    return {"data": [connection_row(item) for item in items], "meta": meta(request)}


@router.post("/connections", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)])
async def register_connection(
    request: Request,
    organization_id: UUID,
    command: GitHubConnectionCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.manage_targets", True)],
) -> dict[str, object]:
    """Register an application-side GitHub publishing connection.

    The GitHub access token is an externally-obtained credential (created in
    GitHub); this stores it encrypted-at-rest and records the connection. This
    is the external credential step, distinct from the application-side
    publishing target configuration (``POST /targets``).
    """
    item = await service.register_github_connection(
        session,
        settings_from_request(request),
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": connection_row(item), "meta": meta(request)}


@router.post("/targets", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)])
async def create_target(
    request: Request,
    organization_id: UUID,
    command: TargetCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.manage_targets", True)],
) -> dict[str, object]:
    """Configure a repository publishing target referencing a GitHub connection."""
    item = await service.create_target(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": target_row(item), "meta": meta(request)}


@router.get("/opportunities", dependencies=[Depends(no_store)])
async def list_opportunities(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    items, has_more = await service.list_opportunities(
        session, organization_id, status_filter=status_filter, limit=limit, offset=offset
    )
    return {
        "data": [opportunity_row(item) for item in items],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
        "meta": meta(request),
    }


@router.post(
    "/opportunities", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def create_opportunity(
    request: Request,
    organization_id: UUID,
    command: OpportunityCreate,
    session: Session,
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.create")],
) -> dict[str, object]:
    item = await service.create_opportunity(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return {"data": opportunity_row(item), "meta": meta(request)}


@router.post("/opportunities/{opportunity_id}/decision", dependencies=[Depends(no_store)])
async def decide_opportunity(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    command: OpportunityDecision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.create")],
) -> dict[str, object]:
    item = await service.decide_opportunity(
        session,
        organization_id,
        opportunity_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": opportunity_row(item), "meta": meta(request)}


@router.get("/summary", dependencies=[Depends(no_store)])
async def summary(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
) -> dict[str, object]:
    return {"data": await service.summary(session, organization_id), "meta": meta(request)}


@router.get("", dependencies=[Depends(no_store)])
async def list_content(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
    status_filter: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    items, has_more = await service.list_items(
        session,
        organization_id,
        status_filter=status_filter,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [item_row(item) for item in items],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
        "meta": meta(request),
    }


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)])
async def create_item(
    request: Request,
    organization_id: UUID,
    command: ItemCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.create")],
) -> dict[str, object]:
    item = await service.create_item(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": item_row(item), "meta": meta(request)}


@router.get("/{item_id}", dependencies=[Depends(no_store)])
async def get_item(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
) -> dict[str, object]:
    item = await service.get_item(session, organization_id, item_id)
    return {"data": item_row(item), "meta": meta(request)}


@router.get("/{item_id}/audit", dependencies=[Depends(no_store)])
async def item_audit(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    await service.get_item(session, organization_id, item_id)
    history = await service.resource_history(
        session,
        organization_id,
        resource_type="content_item",
        resource_id=item_id,
    )
    return {"data": history, "meta": meta(request)}


@router.get("/revisions/{revision_id}/audit", dependencies=[Depends(no_store)])
async def revision_audit(
    request: Request,
    organization_id: UUID,
    revision_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    history = await service.resource_history(
        session,
        organization_id,
        resource_type="content_revision",
        resource_id=revision_id,
    )
    return {"data": history, "meta": meta(request)}


@router.get("/{item_id}/briefs", dependencies=[Depends(no_store)])
async def list_briefs(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
) -> dict[str, object]:
    items = await service.list_briefs(session, organization_id, item_id)
    return {"data": [brief_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/{item_id}/briefs", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def create_brief(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    command: BriefCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.edit")],
) -> dict[str, object]:
    item = await service.create_brief(
        session,
        organization_id,
        item_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": brief_row(item), "meta": meta(request)}


@router.get("/{item_id}/revisions", dependencies=[Depends(no_store)])
async def list_revisions(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
) -> dict[str, object]:
    items = await service.list_revisions(session, organization_id, item_id)
    return {"data": [revision_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/{item_id}/revisions", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def create_revision(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    command: RevisionCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.edit")],
) -> dict[str, object]:
    item = await service.create_revision(
        session,
        organization_id,
        item_id,
        command,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": revision_row(item), "meta": meta(request)}


@router.post(
    "/{item_id}/revisions/ai-draft",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def ai_draft(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    command: AIDraftCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.edit")],
) -> dict[str, object]:
    revision, execution = await service.generate_ai_draft(
        session,
        organization_id,
        item_id,
        command,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {
            **revision_row(revision),
            "ai_execution_id": str(execution.id),
            "requires_human_review": execution.requires_human_review,
            "provider": execution.provider_key,
        },
        "meta": meta(request),
    }


@router.post("/{item_id}/revisions/{revision_id}/decision", dependencies=[Depends(no_store)])
async def decide(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    revision_id: UUID,
    command: ApprovalDecision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.approve", True)],
) -> dict[str, object]:
    del item_id
    item = await service.decide(
        session,
        organization_id,
        revision_id,
        command,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": revision_row(item), "meta": meta(request)}


@router.get("/{item_id}/publications", dependencies=[Depends(no_store)])
async def list_publications(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
) -> dict[str, object]:
    items = await service.list_publications(session, organization_id, item_id)
    return {"data": [publication_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/{item_id}/revisions/{revision_id}/publish",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def publish(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    revision_id: UUID,
    command: PublicationCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.publish", True)],
) -> dict[str, object]:
    item = await service.reserve_publication(
        session,
        organization_id,
        item_id,
        revision_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": publication_row(item), "meta": meta(request)}
