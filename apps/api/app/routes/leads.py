"""Protected consent-aware Leads APIs."""

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
from apps.api.app.products.leads.contracts import CommunicationCreate, ConsentRecord, LeadIntake
from apps.api.app.products.leads.models import Lead
from apps.api.app.products.leads.service import LeadService, set_tenant

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/leads",
    tags=["leads"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = LeadService()
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
async def list_leads(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
) -> dict[str, object]:
    await set_tenant(session, organization_id)
    items = (
        await session.scalars(
            select(Lead)
            .where(Lead.organization_id == organization_id)
            .order_by(Lead.received_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "data": [
            {
                "id": str(x.id),
                "status": x.status,
                "location_id": str(x.location_id) if x.location_id else None,
                "service_id": str(x.service_id) if x.service_id else None,
                "received_at": x.received_at,
            }
            for x in items
        ],
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post("/intake", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)])
async def intake(
    request: Request,
    organization_id: UUID,
    command: LeadIntake,
    session: Session,
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.manage_sources", True)],
) -> dict[str, object]:
    lead, submission, created = await service.intake(session, organization_id, command)
    return {
        "data": {
            "lead_id": str(lead.id),
            "submission_id": str(submission.id),
            "created": created,
            "status": lead.status,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post(
    "/{lead_id}/consents", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def consent(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    command: ConsentRecord,
    session: Session,
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.manage_consent", True)],
) -> dict[str, object]:
    item = await service.record_consent(session, organization_id, lead_id, command)
    return {
        "data": {"id": str(item.id), "channel": item.channel, "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post(
    "/{lead_id}/communications",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def communicate(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    command: CommunicationCreate,
    session: Session,
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.respond")],
) -> dict[str, object]:
    item = await service.plan_communication(session, organization_id, lead_id, command)
    return {
        "data": {"id": str(item.id), "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }
