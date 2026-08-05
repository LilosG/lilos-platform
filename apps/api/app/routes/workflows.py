"""Shared authenticated route for starting persisted, governed workflow runs.

This is the only supported way for a client to obtain a `workflow_run_id`
for a product action (content publication, SEO crawl/analysis, GBP change
publication, GBP post publication, ...). It never accepts a caller-supplied
workflow_run_id as authoritative — it always creates or idempotently
resolves a real, tenant-scoped `WorkflowRun` row and returns its id.
"""

from typing import Annotated, Any
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
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.execution.service import ExecutionService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/workflows",
    tags=["workflows"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = ExecutionService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def policy(key: str) -> Any:
    return Depends(require_authorization(key, ScopeType.ORGANIZATION, AssuranceLevel.AAL1))


def run_row(run: WorkflowRun) -> dict[str, object]:
    return {
        "workflow_run_id": str(run.id),
        "status": run.status,
        "product_key": run.product_key,
    }


class WorkflowRunStart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    location_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)
    input_document: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/{workflow_key}/runs", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def start_workflow_run(
    request: Request,
    organization_id: UUID,
    workflow_key: str,
    command: WorkflowRunStart,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.execute")],
) -> dict[str, object]:
    run = await service.start_named(
        session,
        organization_id,
        workflow_key,
        command.idempotency_key,
        location_id=command.location_id,
        input_document=command.input_document,
        correlation_id=request_correlation_id(request),
        actor_id=principal.platform_user_id,
    )
    return {"data": run_row(run), "meta": {"correlation_id": request_correlation_id(request)}}
