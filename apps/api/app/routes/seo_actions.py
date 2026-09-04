"""Governed execution actions for approved SEO recommendations."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.products.seo.action_service import SEOActionService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/seo",
    tags=["seo-actions"],
    dependencies=[Depends(get_authenticated_principal)],
)
Session = Annotated[AsyncSession, Depends(get_database_session)]
service = SEOActionService()


class SEOActionCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    action_type: Literal["content_article", "content_page", "content_page_optimization"]
    title: str | None = Field(default=None, min_length=1, max_length=300)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def execute_policy() -> object:
    return Depends(
        require_authorization("seo.execute", ScopeType.ORGANIZATION, AssuranceLevel.AAL1)
    )


@router.post(
    "/recommendations/{revision_id}/actions",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def create_action(
    request: Request,
    organization_id: UUID,
    revision_id: UUID,
    command: SEOActionCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, execute_policy()],
) -> dict[str, object]:
    task, item_id, workflow_run_id = await service.create_content_action(
        session,
        organization_id,
        revision_id,
        action_type=command.action_type,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
        title=command.title,
        slug=command.slug,
    )
    return {
        "data": {
            "implementation_task_id": str(task.id),
            "action_type": task.target_type,
            "status": task.status,
            "content_item_id": str(item_id),
            "workflow_run_id": str(workflow_run_id),
            "next": "/content",
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }
