"""Guided Content operator API built on the governed Content domain."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.products.content.contracts import ApprovalDecision
from apps.api.app.products.content.operator_service import (
    ContentOperatorService,
    OperatorPublishRequest,
)
from apps.api.app.products.content.publishing_target_reconciliation import (
    GitHubPublishingTargetReconciler,
)
from apps.api.app.routes.health import settings_from_request

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/content-operations",
    tags=["content"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = ContentOperatorService()
publishing_target_reconciler = GitHubPublishingTargetReconciler(content=service.content)
Session = Annotated[AsyncSession, Depends(get_database_session)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def read_policy() -> object:
    return Depends(
        require_authorization("content.read", ScopeType.ORGANIZATION, AssuranceLevel.AAL1)
    )


def review_policy() -> object:
    return Depends(
        require_authorization("content.approve", ScopeType.ORGANIZATION, AssuranceLevel.AAL2)
    )


def publish_policy() -> object:
    return Depends(
        require_authorization("content.publish", ScopeType.ORGANIZATION, AssuranceLevel.AAL2)
    )


class PublishRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=96)
    publishing_target_id: UUID | None = None
    image: str | None = Field(default=None, max_length=1000)
    image_alt: str | None = Field(default=None, max_length=500)


@router.get("", dependencies=[Depends(no_store)])
async def list_content_operations(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, read_policy()],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items, has_more = await service.list_workspace(
        session,
        organization_id,
        limit=limit,
        offset=offset,
    )
    return {
        "data": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.get("/{item_id}", dependencies=[Depends(no_store)])
async def content_operation_detail(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, read_policy()],
) -> dict[str, object]:
    await publishing_target_reconciler.reconcile(
        session,
        settings_from_request(request),
        organization_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": await service.detail(session, organization_id, item_id),
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post(
    "/{item_id}/revisions/{revision_id}/decision",
    dependencies=[Depends(no_store)],
)
async def decide_content_revision(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    revision_id: UUID,
    command: ApprovalDecision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, review_policy()],
) -> dict[str, object]:
    revision = await service.decide_revision(
        session,
        organization_id,
        item_id,
        revision_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {
            "id": str(revision.id),
            "status": revision.status,
            "revision_number": revision.revision_number,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post(
    "/{item_id}/publish",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def publish_content_item(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    command: PublishRequest,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, publish_policy()],
) -> dict[str, object]:
    await publishing_target_reconciler.reconcile(
        session,
        settings_from_request(request),
        organization_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    publication = await service.publish(
        session,
        organization_id,
        item_id,
        OperatorPublishRequest(
            idempotency_key=command.idempotency_key,
            publishing_target_id=command.publishing_target_id,
            image=command.image,
            image_alt=command.image_alt,
        ),
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )

    # The publication row must exist before the worker can see the run. Attach
    # its authoritative identifier, then expose the same run to the durable
    # queue. enqueue_run_job is idempotent, so replaying the publish request
    # cannot create a second worker job.
    run = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.organization_id == organization_id,
            WorkflowRun.id == publication.workflow_run_id,
        )
    )
    if run is None:
        raise RuntimeError("Content publication workflow run is missing")
    run.input_document = {
        **(run.input_document or {}),
        "publication_id": str(publication.id),
    }
    await service.execution.enqueue_run_job(session, run)
    job = await session.scalar(
        select(Job).where(
            Job.organization_id == organization_id,
            Job.workflow_run_id == run.id,
            Job.idempotency_key == f"run:{run.id}",
        )
    )
    if job is None:
        raise RuntimeError("Content publication worker job was not created")
    job.max_attempts = 30
    await session.flush()

    return {
        "data": {
            "id": str(publication.id),
            "status": publication.status,
            "target_path": publication.target_path,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.get("/{item_id}/publishing-assets", dependencies=[Depends(no_store)])
async def publishing_assets(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    target_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, read_policy()],
) -> dict[str, object]:
    await service.content.get_item(session, organization_id, item_id)
    assets = await service.list_image_assets(
        session,
        settings_from_request(request),
        organization_id,
        target_id,
    )
    return {
        "data": assets,
        "meta": {
            "correlation_id": request_correlation_id(request),
            "count": len(assets),
        },
    }


@router.post(
    "/{item_id}/publications/{publication_id}/recover",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def recover_content_publication(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    publication_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, publish_policy()],
) -> dict[str, object]:
    job = await service.recover_publication(
        session,
        organization_id,
        item_id,
        publication_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {"id": str(job.id), "status": job.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }
