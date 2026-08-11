"""Protected consent-aware Leads APIs."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.contracts import AssignableMemberData, AssignableMemberListResponse
from apps.api.app.access_control.enums import ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.products.leads.contracts import (
    CommunicationCreate,
    ConsentRecord,
    LeadAssignment,
    LeadConversion,
    LeadIntake,
    LeadLoss,
    LeadNoteCreate,
    LeadStatusTransition,
    LeadTaskCreate,
)
from apps.api.app.products.leads.models import (
    Lead,
    LeadCommunication,
    LeadConsent,
    LeadNote,
    LeadTask,
)
from apps.api.app.products.leads.service import LeadService
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/leads",
    tags=["leads"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = LeadService()
access_service = AccessControlService()
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


def lead_row(item: Lead) -> dict[str, object]:
    """Lean, PII-free row for list responses and operational metadata.

    Contact identity (name, email, phone, message) is only returned by the
    single-lead detail endpoint, which is equally permission- and
    tenant-scoped but keeps personal fields out of bulk list payloads.
    """
    return {
        "id": str(item.id),
        "status": item.status,
        "urgency": item.urgency,
        "location_id": str(item.location_id) if item.location_id else None,
        "service_id": str(item.service_id) if item.service_id else None,
        "assigned_to_user_id": str(item.assigned_to_user_id) if item.assigned_to_user_id else None,
        "received_at": item.received_at,
        "acknowledged_at": item.acknowledged_at,
        "first_outbound_attempt_at": item.first_outbound_attempt_at,
        "first_delivered_at": item.first_delivered_at,
        "first_human_contact_at": item.first_human_contact_at,
        "converted_at": item.converted_at,
        "converted_value_cents": item.converted_value_cents,
        "loss_reason": item.loss_reason,
    }


def lead_detail_row(item: Lead) -> dict[str, object]:
    return {
        **lead_row(item),
        "first_name": item.first_name,
        "last_name": item.last_name,
        "normalized_email": item.normalized_email,
        "normalized_phone": item.normalized_phone,
        "message": item.message,
    }


def note_row(item: LeadNote) -> dict[str, object]:
    return {
        "id": str(item.id),
        "author_user_id": str(item.author_user_id) if item.author_user_id else None,
        "body": item.body,
        "created_at": item.created_at,
    }


def task_row(item: LeadTask) -> dict[str, object]:
    return {
        "id": str(item.id),
        "title": item.title,
        "description": item.description,
        "due_at": item.due_at,
        "assigned_to_user_id": str(item.assigned_to_user_id) if item.assigned_to_user_id else None,
        "status": item.status,
        "completed_at": item.completed_at,
    }


def communication_row(item: LeadCommunication) -> dict[str, object]:
    return {
        "id": str(item.id),
        "direction": item.direction,
        "channel": item.channel,
        "status": item.status,
        "message_reference": item.message_reference,
        "sent_at": item.sent_at,
        "delivered_at": item.delivered_at,
        "failed_at": item.failed_at,
    }


def consent_row(item: LeadConsent) -> dict[str, object]:
    return {
        "id": str(item.id),
        "channel": item.channel,
        "consent_type": item.consent_type,
        "status": item.status,
        "captured_at": item.captured_at,
        "withdrawn_at": item.withdrawn_at,
    }


@router.get("", dependencies=[Depends(no_store)])
async def list_leads(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
    status_filter: str | None = None,
    urgency_filter: str | None = None,
    assigned_to_user_id: UUID | None = None,
    location_id: UUID | None = None,
    search: str | None = None,
    sort: str = "recent",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    items, has_more = await service.list_leads(
        session,
        organization_id,
        status_filter=status_filter,
        urgency_filter=urgency_filter,
        assigned_to_user_id=assigned_to_user_id,
        location_id=location_id,
        search=search,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [lead_row(item) for item in items],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
        "meta": meta(request),
    }


@router.get("/summary", dependencies=[Depends(no_store)])
async def summary(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
) -> dict[str, object]:
    return {"data": await service.summary(session, organization_id), "meta": meta(request)}


@router.get("/sources/performance", dependencies=[Depends(no_store)])
async def source_performance(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
) -> dict[str, object]:
    return {
        "data": await service.source_performance(session, organization_id),
        "meta": meta(request),
    }


@router.get(
    "/assignees",
    response_model=AssignableMemberListResponse,
    dependencies=[Depends(no_store)],
)
async def list_assignees(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.assign")],
) -> AssignableMemberListResponse:
    """List teammates who may be assigned leads for this organization.

    Organization-scoped, tenant-isolated, and authorized through the existing
    ``leads.assign`` access-control policy so only operators who can actually
    assign leads learn who is assignable. Returns the focused fields the
    picker needs; no email, no fabricated names, no raw SQL bypass, and no
    parallel membership/user subsystem — it reads the same authoritative
    membership, user-profile, and role-assignment tables every other access
    read uses.
    """
    members = await access_service.list_assignable_members(session, organization_id)
    return AssignableMemberListResponse(
        data=[
            AssignableMemberData(
                user_profile_id=member.user_profile_id,
                display_name=member.display_name,
                membership_status=member.membership_status,
                membership_type=member.membership_type,
                role_keys=member.role_keys,
            )
            for member in members
        ],
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.get("/{lead_id}", dependencies=[Depends(no_store)])
async def get_lead(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
) -> dict[str, object]:
    lead = await service.get(session, organization_id, lead_id)
    return {"data": lead_detail_row(lead), "meta": meta(request)}


@router.get("/{lead_id}/notes", dependencies=[Depends(no_store)])
async def list_notes(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
) -> dict[str, object]:
    items = await service.list_notes(session, organization_id, lead_id)
    return {"data": [note_row(item) for item in items], "meta": meta(request)}


@router.get("/{lead_id}/tasks", dependencies=[Depends(no_store)])
async def list_tasks(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
) -> dict[str, object]:
    items = await service.list_tasks(session, organization_id, lead_id)
    return {"data": [task_row(item) for item in items], "meta": meta(request)}


@router.get("/{lead_id}/communications", dependencies=[Depends(no_store)])
async def list_communications(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
) -> dict[str, object]:
    items = await service.list_communications(session, organization_id, lead_id)
    return {"data": [communication_row(item) for item in items], "meta": meta(request)}


@router.get("/{lead_id}/consents", dependencies=[Depends(no_store)])
async def list_consents(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("leads.read")],
) -> dict[str, object]:
    items = await service.list_consents(session, organization_id, lead_id)
    return {"data": [consent_row(item) for item in items], "meta": meta(request)}


@router.get("/{lead_id}/audit", dependencies=[Depends(no_store)])
async def lead_audit(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    await service.get(session, organization_id, lead_id)
    history = await service.resource_history(
        session, organization_id, resource_type="lead", resource_id=lead_id
    )
    return {"data": history, "meta": meta(request)}


@router.post("/intake", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)])
async def intake(
    request: Request,
    organization_id: UUID,
    command: LeadIntake,
    session: Session,
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.manage_sources", True)],
) -> dict[str, object]:
    lead, submission, created = await service.intake(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return {
        "data": {
            "lead_id": str(lead.id),
            "submission_id": str(submission.id),
            "created": created,
            "status": lead.status,
        },
        "meta": meta(request),
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
    item = await service.record_consent(
        session, organization_id, lead_id, command, correlation_id=request_correlation_id(request)
    )
    return {
        "data": {"id": str(item.id), "channel": item.channel, "status": item.status},
        "meta": meta(request),
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
    item = await service.plan_communication(
        session, organization_id, lead_id, command, correlation_id=request_correlation_id(request)
    )
    return {
        "data": {"id": str(item.id), "status": item.status},
        "meta": meta(request),
    }


@router.post("/{lead_id}/assign", dependencies=[Depends(no_store)])
async def assign(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    command: LeadAssignment,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.assign")],
) -> dict[str, object]:
    lead = await service.assign(
        session,
        organization_id,
        lead_id,
        command.assigned_to_user_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": lead_detail_row(lead), "meta": meta(request)}


@router.post("/{lead_id}/status", dependencies=[Depends(no_store)])
async def transition_status(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    command: LeadStatusTransition,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.assign")],
) -> dict[str, object]:
    lead = await service.transition_status(
        session,
        organization_id,
        lead_id,
        command.to_status,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
        safe_reason=command.safe_reason,
    )
    return {"data": lead_detail_row(lead), "meta": meta(request)}


@router.post("/{lead_id}/convert", dependencies=[Depends(no_store)])
async def convert(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    command: LeadConversion,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.assign")],
) -> dict[str, object]:
    lead = await service.record_conversion(
        session,
        organization_id,
        lead_id,
        converted_value_cents=command.converted_value_cents,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": lead_detail_row(lead), "meta": meta(request)}


@router.post("/{lead_id}/loss", dependencies=[Depends(no_store)])
async def loss(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    command: LeadLoss,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.assign")],
) -> dict[str, object]:
    lead = await service.record_loss(
        session,
        organization_id,
        lead_id,
        to_status=command.to_status,
        loss_reason=command.loss_reason,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": lead_detail_row(lead), "meta": meta(request)}


@router.post(
    "/{lead_id}/notes", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def add_note(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    command: LeadNoteCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.respond")],
) -> dict[str, object]:
    note = await service.add_note(
        session,
        organization_id,
        lead_id,
        author_id=principal.platform_user_id,
        body=command.body,
        correlation_id=request_correlation_id(request),
    )
    return {"data": note_row(note), "meta": meta(request)}


@router.post(
    "/{lead_id}/tasks", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def create_task(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    command: LeadTaskCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.respond")],
) -> dict[str, object]:
    task = await service.create_task(
        session,
        organization_id,
        lead_id,
        title=command.title,
        description=command.description,
        due_at=command.due_at,
        assigned_to_user_id=command.assigned_to_user_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": task_row(task), "meta": meta(request)}


@router.post("/{lead_id}/tasks/{task_id}/complete", dependencies=[Depends(no_store)])
async def complete_task(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    task_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("leads.respond")],
) -> dict[str, object]:
    task = await service.complete_task(
        session,
        organization_id,
        lead_id,
        task_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": task_row(task), "meta": meta(request)}
