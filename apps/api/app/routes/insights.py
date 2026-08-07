"""Protected Insights APIs backed by real cross-product activity data."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import (
    get_authenticated_principal,
)
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.insights.aggregation_service import InsightsService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/insights",
    tags=["insights"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = InsightsService()
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


@router.get("/summary", dependencies=[Depends(no_store)])
async def summary(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("insights.read")],
) -> dict[str, object]:
    return {"data": await service.summary(session, organization_id), "meta": meta(request)}
