"""Scoped, read-only Reports projection over canonical report and metric records."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.insights.models import (
    InsightSource,
    MetricDefinition,
    MetricObservation,
    ReportDefinition,
    ReportDelivery,
    ReportRevision,
)
from apps.api.app.notifications.models import NotificationDelivery
from apps.api.app.routes.command_center_reviews import private
from apps.api.app.routes.command_center_search import allowed
from apps.api.app.routes.insights import Session

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center/reports",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(private)],
)


class Blocker(BaseModel):
    code: Literal[
        "NO_METRICS", "INVALID_METRIC_REFERENCE", "METRIC_UNDEFINED",
        "DATA_MISSING", "DATA_STALE", "DATA_PARTIAL", "SOURCE_UNAVAILABLE",
        "DEFINITION_INACTIVE", "UNSUPPORTED_SCOPE",
    ]
    metric_id: UUID | None = None


class MetricState(BaseModel):
    metric_id: UUID
    name: str
    state: str
    source: str | None
    period_start: datetime | None
    period_end: datetime | None
    last_synced_at: datetime | None


class DeliveryState(BaseModel):
    id: UUID
    status: Literal["queued", "sent", "failed", "unavailable"]
    created_at: datetime
    artifact_reference: str | None


class ReportItem(BaseModel):
    id: UUID
    name: str
    definition_status: str
    readiness: Literal["ready", "not_ready"]
    data_state: Literal["ready", "missing", "stale", "partial", "unavailable"]
    blockers: list[Blocker]
    metrics: list[MetricState]
    generation: Literal["queued", "generating", "ready", "sent", "failed", "unavailable"]
    revision_id: UUID | None
    revision_status: str | None
    revision_created_at: datetime | None
    artifact_reference: str | None
    deliveries: list[DeliveryState]


class ReportsWorkspace(BaseModel):
    organization_id: UUID
    observed_at: datetime
    reports: list[ReportItem]
    schedule_state: Literal["unavailable_no_canonical_report_schedule"]
    generation_state: Literal["unavailable_no_canonical_report_workflow"]
    history_state: Literal["bounded_partial"]
    source_state: Literal["canonical_reports_and_metrics"]


def metric_id(reference: object) -> UUID | None:
    candidate = reference.get("metric_definition_id") if isinstance(reference, dict) else reference
    try:
        return UUID(str(candidate))
    except (ValueError, TypeError, AttributeError):
        return None


def delivery_state(report: ReportDelivery, notification: NotificationDelivery | None) -> DeliveryState:
    status: Literal["queued", "sent", "failed", "unavailable"] = "unavailable"
    if report.status in {"failed", "dead_lettered"} or (
        notification and notification.status in {"failed", "dead_lettered"}
    ):
        status = "failed"
    elif report.status == "delivered" and notification and notification.status == "delivered":
        status = "sent"
    elif report.status in {"pending", "queued", "sending"}:
        status = "queued"
    return DeliveryState(
        id=report.id, status=status, created_at=report.created_at,
        artifact_reference=report.artifact_reference,
    )


def generation_state(revision: ReportRevision | None, deliveries: list[DeliveryState]) -> Literal[
    "queued", "generating", "ready", "sent", "failed", "unavailable"
]:
    if any(item.status == "sent" for item in deliveries):
        return "sent"
    if revision is None:
        return "unavailable"
    if revision.status in {"failed", "error"}:
        return "failed"
    if revision.status in {"queued", "pending"}:
        return "queued"
    if revision.status in {"generating", "running"}:
        return "generating"
    if revision.status in {"approved", "published", "ready", "delivered"}:
        return "ready"
    return "unavailable"


class ReportsEnvelope(BaseModel):
    data: ReportsWorkspace


@router.get("/", response_model=ReportsEnvelope)
async def reports_workspace(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
) -> ReportsEnvelope:
    if not await allowed(session, principal, organization_id, request, "insights.read"):
        from fastapi import HTTPException
        raise HTTPException(403, "Reports read permission required")

    now = datetime.now(UTC)
    definitions = list(await session.scalars(
        select(ReportDefinition).where(ReportDefinition.organization_id == organization_id)
        .order_by(ReportDefinition.name, ReportDefinition.id).limit(100)
    ))
    revisions = list(await session.scalars(
        select(ReportRevision).where(ReportRevision.organization_id == organization_id)
        .order_by(ReportRevision.created_at.desc(), ReportRevision.id.desc()).limit(500)
    ))
    deliveries = list(await session.scalars(
        select(ReportDelivery).where(ReportDelivery.organization_id == organization_id)
        .order_by(ReportDelivery.created_at.desc(), ReportDelivery.id.desc()).limit(500)
    ))
    observations = list(await session.scalars(
        select(MetricObservation).where(
            MetricObservation.organization_id == organization_id,
            MetricObservation.location_id.is_(None),
            MetricObservation.website_id.is_(None),
        ).order_by(MetricObservation.period_end.desc(), MetricObservation.id.desc())
    ))
    sources = {s.id: s for s in await session.scalars(
        select(InsightSource).where(InsightSource.organization_id == organization_id)
    )}
    metric_ids = {key for d in definitions for ref in d.metric_references if (key := metric_id(ref))}
    metrics = {m.id: m for m in await session.scalars(
        select(MetricDefinition).where(MetricDefinition.id.in_(metric_ids))
    )} if metric_ids else {}
    latest_observation: dict[UUID, MetricObservation] = {}
    for observation in observations:
        latest_observation.setdefault(observation.metric_definition_id, observation)
    latest_revision: dict[UUID, ReportRevision] = {}
    for revision in revisions:
        latest_revision.setdefault(revision.report_definition_id, revision)
    notification_ids = {d.notification_delivery_id for d in deliveries if d.notification_delivery_id}
    notifications = {n.id: n for n in await session.scalars(
        select(NotificationDelivery).where(
            NotificationDelivery.organization_id == organization_id,
            NotificationDelivery.id.in_(notification_ids),
        )
    )} if notification_ids else {}
    by_revision: dict[UUID, list[DeliveryState]] = {}
    for delivery in deliveries:
        by_revision.setdefault(delivery.report_revision_id, []).append(
            delivery_state(delivery, notifications.get(delivery.notification_delivery_id))
        )

    result: list[ReportItem] = []
    for definition in definitions:
        blockers: list[Blocker] = []
        states: list[MetricState] = []
        if definition.requested_scope not in ({}, {"organization_id": str(organization_id)}):
            blockers.append(Blocker(code="UNSUPPORTED_SCOPE"))
        if definition.status != "active":
            blockers.append(Blocker(code="DEFINITION_INACTIVE"))
        if not definition.metric_references:
            blockers.append(Blocker(code="NO_METRICS"))
        for reference in definition.metric_references:
            key = metric_id(reference)
            if key is None:
                blockers.append(Blocker(code="INVALID_METRIC_REFERENCE"))
                continue
            metric = metrics.get(key)
            if metric is None:
                blockers.append(Blocker(code="METRIC_UNDEFINED", metric_id=key))
                continue
            observation = latest_observation.get(key)
            source = sources.get(observation.source_id) if observation else None
            state = observation.quality_state if observation else "missing"
            code = None
            if observation is None:
                code = "DATA_MISSING"
            elif source is None or source.status not in {"active", "connected", "available"}:
                state, code = "unavailable", "SOURCE_UNAVAILABLE"
            elif observation.quality_state in {"partial", "delayed"}:
                code = "DATA_PARTIAL"
            elif observation.quality_state in {"missing", "invalid", "suppressed"}:
                code = "DATA_MISSING"
            elif observation.quality_state in {"unavailable", "unsupported"}:
                code = "SOURCE_UNAVAILABLE"
            elif observation.quality_state == "stale" or (
                metric.freshness_seconds >= 0
                and (observation.period_end < now - timedelta(seconds=metric.freshness_seconds)
                     or source.last_synced_at is None
                     or source.last_synced_at < now - timedelta(seconds=metric.freshness_seconds))
            ):
                state, code = "stale", "DATA_STALE"
            elif observation.quality_state not in {"valid", "zero"}:
                code = "DATA_PARTIAL"
            if code:
                blockers.append(Blocker(code=code, metric_id=key))
            states.append(MetricState(
                metric_id=key, name=metric.name, state=state,
                source=source.key if source else None,
                period_start=observation.period_start if observation else None,
                period_end=observation.period_end if observation else None,
                last_synced_at=source.last_synced_at if source else None,
            ))
        codes = {b.code for b in blockers}
        data_state: Literal["ready", "missing", "stale", "partial", "unavailable"] = "ready"
        if codes & {"SOURCE_UNAVAILABLE", "INVALID_METRIC_REFERENCE", "METRIC_UNDEFINED", "NO_METRICS", "UNSUPPORTED_SCOPE"}:
            data_state = "unavailable"
        elif "DATA_MISSING" in codes:
            data_state = "missing"
        elif "DATA_STALE" in codes:
            data_state = "stale"
        elif "DATA_PARTIAL" in codes:
            data_state = "partial"
        revision = latest_revision.get(definition.id)
        report_revision_ids = {r.id for r in revisions if r.report_definition_id == definition.id}
        history = [d for r in report_revision_ids for d in by_revision.get(r, [])]
        history.sort(key=lambda d: (d.created_at, d.id), reverse=True)
        current_deliveries = by_revision.get(revision.id, []) if revision else []
        result.append(ReportItem(
            id=definition.id, name=definition.name, definition_status=definition.status,
            readiness="ready" if not blockers else "not_ready",
            data_state=data_state, blockers=blockers, metrics=states,
            generation=generation_state(revision, current_deliveries),
            revision_id=revision.id if revision else None,
            revision_status=revision.status if revision else None,
            revision_created_at=revision.created_at if revision else None,
            artifact_reference=current_deliveries[0].artifact_reference if current_deliveries else None,
            deliveries=history[:20],
        ))
    return ReportsEnvelope(data=ReportsWorkspace(
        organization_id=organization_id, observed_at=now, reports=result,
        schedule_state="unavailable_no_canonical_report_schedule",
        generation_state="unavailable_no_canonical_report_workflow",
        history_state="bounded_partial",
        source_state="canonical_reports_and_metrics",
    ))
