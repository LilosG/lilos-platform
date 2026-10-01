"""Bounded read projections of canonical Leads evidence; no provider calls or writes."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, get_args
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select

from apps.api.app.access_control.contracts import AssignableMemberData
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.models import Location
from apps.api.app.products.leads.contracts import LeadStatusTransition
from apps.api.app.products.leads.errors import LeadNotFoundError
from apps.api.app.products.leads.models import (
    CRMLeadMapping,
    Lead,
    LeadCommunication,
    LeadConsent,
    LeadNote,
    LeadSource,
    LeadStatusHistory,
    LeadSubmission,
    LeadTask,
)
from apps.api.app.products.leads.service import can_transition, set_tenant
from apps.api.app.routes.command_center_reviews import ReviewHistory, private
from apps.api.app.routes.command_center_search import allowed
from apps.api.app.routes.leads import Session, access_service, policy, service

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center/leads",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(private)],
)


class LeadDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LeadLocation(LeadDTO):
    id: UUID
    name: str


class LeadSourceEvidence(LeadDTO):
    id: UUID
    name: str
    source_type: str
    status: str
    location_id: UUID | None
    integration_connection_id: UUID | None
    provider: str | None
    connection_status: str | None
    last_intake_at: datetime | None
    intake_recency: Literal["recent", "stale", "unavailable"]
    sync_state: Literal["unavailable_no_canonical_sync_record"] = (
        "unavailable_no_canonical_sync_record"
    )
    quality: Literal["partial"] = "partial"
    lead_count: int
    recorded_conversions: int


class LeadInventoryItem(LeadDTO):
    id: UUID
    location_id: UUID | None
    source_id: UUID
    status: str
    urgency: str
    received_at: datetime
    acknowledged_at: datetime | None
    first_outbound_attempt_at: datetime | None
    first_delivered_at: datetime | None
    first_human_contact_at: datetime | None
    converted_at: datetime | None
    converted_value_cents: int | None
    loss_reason: str | None
    assigned_to_user_id: UUID | None
    duplicate_of_lead_id: UUID | None
    outcome: Literal["recorded_conversion", "recorded_loss", "unknown"]
    attribution: Literal["source_identity_only_no_campaign_or_landing_page"] = (
        "source_identity_only_no_campaign_or_landing_page"
    )


class LeadsWorkspace(LeadDTO):
    organization_id: UUID
    location_id: UUID | None
    locations: list[LeadLocation]
    sources: list[LeadSourceEvidence]
    items: list[LeadInventoryItem]
    inventory_count: int | None
    recorded_conversions: int | None
    next_offset: int | None
    period: Literal["all_persisted_records"] = "all_persisted_records"
    quality: Literal["partial", "unavailable"]
    downstream_outcomes: Literal["unavailable_no_booking_sales_jobs_or_revenue_source"] = (
        "unavailable_no_booking_sales_jobs_or_revenue_source"
    )


class LeadContact(LeadInventoryItem):
    first_name: str | None
    last_name: str | None
    normalized_email: str | None
    normalized_phone: str | None
    message: str | None
    location_match_status: str


class LeadNoteEvidence(LeadDTO):
    id: UUID
    body: str
    author_user_id: UUID | None
    created_at: datetime


class LeadTaskEvidence(LeadDTO):
    id: UUID
    title: str
    description: str | None
    due_at: datetime | None
    assigned_to_user_id: UUID | None
    status: str
    completed_at: datetime | None


class LeadConsentEvidence(LeadDTO):
    id: UUID
    channel: str
    consent_type: str
    status: str
    source: str
    disclosure_version: str
    evidence_reference: str
    captured_at: datetime
    withdrawn_at: datetime | None


class LeadCommunicationEvidence(LeadDTO):
    id: UUID
    direction: str
    channel: str
    status: str
    message_reference: str
    provider_message_id: str | None
    workflow_run_id: UUID
    workflow_status: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    failed_at: datetime | None


class LeadSubmissionEvidence(LeadDTO):
    id: UUID
    source_id: UUID
    external_submission_id: str
    received_at: datetime
    status: str


class LeadStateEvidence(LeadDTO):
    id: UUID
    from_status: str | None
    to_status: str
    actor_type: str
    safe_reason: str | None
    created_at: datetime


class LeadCRMEvidence(LeadDTO):
    id: UUID
    connection_id: UUID
    external_lead_id: str
    sync_status: str


class LeadCapabilities(LeadDTO):
    can_assign: bool
    can_respond: bool
    can_manage_consent: bool
    can_read_audit: bool
    allowed_statuses: list[str]
    can_record_outcome: bool


class LeadWorkspaceDetail(LeadDTO):
    organization_id: UUID
    lead: LeadContact
    source: LeadSourceEvidence
    notes: list[LeadNoteEvidence]
    tasks: list[LeadTaskEvidence]
    consents: list[LeadConsentEvidence]
    communications: list[LeadCommunicationEvidence]
    submissions: list[LeadSubmissionEvidence]
    states: list[LeadStateEvidence]
    crm_mappings: list[LeadCRMEvidence]
    history: list[ReviewHistory]
    assignees: list[AssignableMemberData]
    capabilities: LeadCapabilities
    history_limit: Literal[50] = 50
    history_quality: Literal["bounded_partial"] = "bounded_partial"
    downstream_outcomes: Literal["unavailable_no_booking_sales_jobs_or_revenue_source"] = (
        "unavailable_no_booking_sales_jobs_or_revenue_source"
    )


def inventory(row: Lead) -> LeadInventoryItem:
    return LeadInventoryItem.model_validate(
        {
            **{
                key: getattr(row, key)
                for key in LeadInventoryItem.model_fields
                if key not in {"outcome", "attribution"}
            },
            "outcome": "recorded_conversion"
            if row.converted_at is not None
            else "recorded_loss"
            if row.loss_reason is not None
            else "unknown",
        }
    )


async def sources_evidence(
    session: Session, org: UUID, sources: list[LeadSource], location: UUID | None
) -> list[LeadSourceEvidence]:
    scope = [Lead.organization_id == org, Lead.source_id.in_([s.id for s in sources])]
    if location is not None:
        scope.append(Lead.location_id == location)
    counts = {
        r.source_id: (r.total, r.converted)
        for r in await session.execute(
            select(
                Lead.source_id,
                func.count(Lead.id).label("total"),
                func.count(Lead.id).filter(Lead.converted_at.is_not(None)).label("converted"),
            )
            .where(*scope)
            .group_by(Lead.source_id)
        )
    }
    latest = {
        r.source_id: r.latest
        for r in await session.execute(
            select(LeadSubmission.source_id, func.max(LeadSubmission.received_at).label("latest"))
            .join(
                Lead,
                (Lead.id == LeadSubmission.lead_id)
                & (Lead.organization_id == LeadSubmission.organization_id),
            )
            .where(*scope, LeadSubmission.organization_id == org)
            .group_by(LeadSubmission.source_id)
        )
    }
    connections = {
        r.id: (r.status, r.key)
        for r in await session.execute(
            select(IntegrationConnection.id, IntegrationConnection.status, Provider.key)
            .join(Provider, Provider.id == IntegrationConnection.provider_id)
            .where(
                IntegrationConnection.organization_id == org,
                IntegrationConnection.id.in_(
                    [s.integration_connection_id for s in sources if s.integration_connection_id]
                ),
            )
        )
    }
    result = []
    for source in sources:
        connection = connections.get(source.integration_connection_id)
        received = latest.get(source.id)
        count, converted = counts.get(source.id, (0, 0))
        result.append(
            LeadSourceEvidence(
                **{
                    key: getattr(source, key)
                    for key in (
                        "id",
                        "name",
                        "source_type",
                        "status",
                        "location_id",
                        "integration_connection_id",
                    )
                },
                provider=connection[1] if connection else None,
                connection_status=connection[0] if connection else None,
                last_intake_at=received,
                intake_recency="unavailable"
                if received is None
                else "stale"
                if received < datetime.now(UTC) - timedelta(days=1)
                else "recent",
                lead_count=count,
                recorded_conversions=converted,
            )
        )
    return result


async def check_location(session: Session, org: UUID, location: UUID | None) -> None:
    if location is not None and not await session.scalar(
        select(Location.id).where(Location.organization_id == org, Location.id == location)
    ):
        raise LeadNotFoundError


@router.get("", response_model=LeadsWorkspace)
async def workspace(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[object, policy("leads.read")],
    location_id: UUID | None = None,
    offset: int = Query(0, ge=0, le=100000),
) -> LeadsWorkspace:
    await set_tenant(session, organization_id)
    await check_location(session, organization_id, location_id)
    locations = list(
        await session.scalars(
            select(Location)
            .where(Location.organization_id == organization_id)
            .order_by(Location.name, Location.id)
        )
    )
    scope = [Lead.organization_id == organization_id]
    if location_id is not None:
        scope.append(Lead.location_id == location_id)
    rows = list(
        await session.scalars(
            select(Lead)
            .where(*scope)
            .order_by(Lead.received_at.desc(), Lead.id)
            .limit(51)
            .offset(offset)
        )
    )
    # Include referenced sources even when source configuration and intake location differ.
    source_scope = [
        LeadSource.organization_id == organization_id,
        or_(
            *(
                [LeadSource.location_id == location_id, LeadSource.location_id.is_(None)]
                if location_id
                else [LeadSource.organization_id == organization_id]
            ),
            LeadSource.id.in_(select(Lead.source_id).where(*scope)),
        ),
    ]
    sources = list(
        await session.scalars(
            select(LeadSource)
            .where(*source_scope)
            .order_by(LeadSource.name, LeadSource.id)
            .limit(101)
        )
    )
    count, converted = (
        await session.execute(
            select(
                func.count(Lead.id), func.count(Lead.id).filter(Lead.converted_at.is_not(None))
            ).where(*scope)
        )
    ).one()
    return LeadsWorkspace(
        organization_id=organization_id,
        location_id=location_id,
        locations=[LeadLocation.model_validate(row) for row in locations],
        sources=await sources_evidence(session, organization_id, sources[:100], location_id),
        items=[inventory(row) for row in rows[:50]],
        inventory_count=count if sources or count else None,
        recorded_conversions=converted if sources or count else None,
        next_offset=offset + 50 if len(rows) > 50 else None,
        quality="partial" if sources or count else "unavailable",
    )


@router.get("/{lead_id}", response_model=LeadWorkspaceDetail)
async def detail(
    request: Request,
    organization_id: UUID,
    lead_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[object, policy("leads.read")],
    location_id: UUID | None = None,
) -> LeadWorkspaceDetail:
    row = await service.get(session, organization_id, lead_id)
    await check_location(session, organization_id, location_id)
    if location_id is not None and row.location_id != location_id:
        raise LeadNotFoundError
    source = await service.get_source(session, organization_id, row.source_id)
    assign = await allowed(session, principal, organization_id, request, "leads.assign")
    respond = await allowed(session, principal, organization_id, request, "leads.respond")
    consent = await allowed(
        session, principal, organization_id, request, "leads.manage_consent", aal2=True
    )
    audit = await allowed(session, principal, organization_id, request, "audit.read")

    history_time = {
        LeadNote: LeadNote.created_at,
        LeadTask: LeadTask.created_at,
        LeadConsent: LeadConsent.captured_at,
        LeadCommunication: LeadCommunication.created_at,
        LeadSubmission: LeadSubmission.received_at,
        LeadStatusHistory: LeadStatusHistory.created_at,
        CRMLeadMapping: CRMLeadMapping.updated_at,
    }

    async def records(
        model: type[LeadNote]
        | type[LeadTask]
        | type[LeadConsent]
        | type[LeadCommunication]
        | type[LeadSubmission]
        | type[LeadStatusHistory]
        | type[CRMLeadMapping],
    ) -> list[object]:
        return list(
            await session.scalars(
                select(model)
                .where(model.organization_id == organization_id, model.lead_id == lead_id)
                .order_by(history_time[model].desc(), model.id.desc())
                .limit(50)
            )
        )

    communication_rows = await records(LeadCommunication)
    runs = {
        r.id: r.status
        for r in await session.scalars(
            select(WorkflowRun).where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id.in_(
                    [
                        r.workflow_run_id
                        for r in communication_rows
                        if isinstance(r, LeadCommunication)
                    ]
                ),
            )
        )
    }
    communications = []
    for item in communication_rows:
        assert isinstance(item, LeadCommunication)
        communications.append(
            LeadCommunicationEvidence.model_validate(
                {
                    **{
                        key: getattr(item, key)
                        for key in LeadCommunicationEvidence.model_fields
                        if key != "workflow_status"
                    },
                    "workflow_status": runs.get(item.workflow_run_id),
                }
            )
        )
    return LeadWorkspaceDetail(
        organization_id=organization_id,
        lead=LeadContact(
            **inventory(row).model_dump(),
            **{
                key: getattr(row, key)
                for key in (
                    "first_name",
                    "last_name",
                    "normalized_email",
                    "normalized_phone",
                    "message",
                    "location_match_status",
                )
            },
        ),
        source=(await sources_evidence(session, organization_id, [source], row.location_id))[0],
        notes=[LeadNoteEvidence.model_validate(r) for r in await records(LeadNote)],
        tasks=[LeadTaskEvidence.model_validate(r) for r in await records(LeadTask)],
        consents=[LeadConsentEvidence.model_validate(r) for r in await records(LeadConsent)],
        communications=communications,
        submissions=[
            LeadSubmissionEvidence.model_validate(r) for r in await records(LeadSubmission)
        ],
        states=[LeadStateEvidence.model_validate(r) for r in await records(LeadStatusHistory)],
        crm_mappings=[LeadCRMEvidence.model_validate(r) for r in await records(CRMLeadMapping)],
        history=[
            ReviewHistory.model_validate(r)
            for r in await service.resource_history(
                session, organization_id, resource_type="lead", resource_id=lead_id
            )
        ]
        if audit
        else [],
        assignees=[
            AssignableMemberData(
                user_profile_id=m.user_profile_id,
                display_name=m.display_name,
                membership_status=m.membership_status,
                membership_type=m.membership_type,
                role_keys=m.role_keys,
            )
            for m in await access_service.list_assignable_members(session, organization_id)
        ]
        if assign
        else [],
        capabilities=LeadCapabilities(
            can_assign=assign,
            can_respond=respond,
            can_manage_consent=consent,
            can_read_audit=audit,
            allowed_statuses=[
                s
                for s in get_args(LeadStatusTransition.model_fields["to_status"].annotation)
                if assign and can_transition(row.status, s)
            ],
            can_record_outcome=assign and can_transition(row.status, "converted"),
        ),
    )
