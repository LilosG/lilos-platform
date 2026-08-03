"""Protected governed Content APIs."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.products.content.contracts import (
    ApprovalDecision,
    PublicationCreate,
    RevisionCreate,
)
from apps.api.app.products.content.models import ContentItem
from apps.api.app.products.content.service import ContentService

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


@router.get("", dependencies=[Depends(no_store)])
async def list_content(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("content.read")],
) -> dict[str, object]:
    items = (
        await session.scalars(
            select(ContentItem)
            .where(ContentItem.organization_id == organization_id)
            .order_by(ContentItem.created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "data": [
            {
                "id": str(x.id),
                "title": x.title,
                "content_type": x.content_type,
                "status": x.status,
                "location_id": str(x.location_id) if x.location_id else None,
            }
            for x in items
        ],
        "meta": {"correlation_id": request_correlation_id(request)},
    }


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
        session, organization_id, item_id, command, principal.platform_user_id
    )
    return {
        "data": {
            "id": str(item.id),
            "revision": item.revision_number,
            "status": item.status,
            "validation": item.validation_document,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
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
    item = await service.decide(
        session, organization_id, revision_id, command, principal.platform_user_id
    )
    return {
        "data": {"id": str(item.id), "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }


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
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("content.publish", True)],
) -> dict[str, object]:
    item = await service.reserve_publication(
        session, organization_id, item_id, revision_id, command
    )
    return {
        "data": {
            "publication_id": str(item.id),
            "status": item.status,
            "target_path": item.target_path,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }
