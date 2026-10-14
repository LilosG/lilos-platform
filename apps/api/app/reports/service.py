"""Persistence of the monthly report: generate, edit the narrative, approve, record as sent.

Reports are saved snapshots. A revision's numbers are computed once and never recomputed; an
approved revision is immutable (the database refuses any change to it), and a regeneration whose
data differs becomes a new draft beside it. Nothing here emails or notifies anyone: delivery is a
person telling the client, recorded here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.insights.models import ReportDefinition, ReportDelivery, ReportRevision
from apps.api.app.products.gbp.performance_enums import GBPPerformanceMetric
from apps.api.app.reports.contracts import (
    DEFINITION_KEY,
    SNAPSHOT_SCHEMA_VERSION,
    NarrativeOrigin,
    ReportNarrative,
    ReportReadiness,
    ReportSnapshot,
    ReportStatus,
)
from apps.api.app.reports.errors import (
    ReportAlreadyApprovedError,
    ReportDataMissingError,
    ReportNarrativeEmptyError,
    ReportNotApprovedError,
    ReportNotEditableError,
    ReportNotFoundError,
    ReportRevisionSupersededError,
    ReportSentDateInvalidError,
)
from apps.api.app.reports.snapshot import (
    build_snapshot,
    canonical_json,
    data_hash,
    report_today,
    require_ended,
)

REVISION_DRAFT = "draft"
# The database freezes a revision once it is "approved"; sending is recorded as a delivery.
REVISION_APPROVED = "approved"
DELIVERY_SENT = "sent"
AUDIT_PRODUCT = "insights"
METRIC_KEYS: list[str] = [
    "report.snapshot",
    *[f"gbp.{metric.value}" for metric in GBPPerformanceMetric],
    "gbp.search_keywords",
    "reviews.monthly",
    "search_console.month",
    "ga4.organicLanding.sessions",
]
METRIC_VERSIONS: list[dict[str, str | int]] = [
    {"key": key, "version": SNAPSHOT_SCHEMA_VERSION if key == "report.snapshot" else 1}
    for key in METRIC_KEYS
]


@dataclass(frozen=True, slots=True)
class StoredReport:
    """A revision with its envelope parsed: computed snapshot, narrative and data hash."""

    revision: ReportRevision
    snapshot: ReportSnapshot
    narrative: ReportNarrative
    data_hash: str

    @property
    def month(self) -> date:
        return self.revision.period_month

    @property
    def is_approved(self) -> bool:
        return self.revision.status == REVISION_APPROVED


def envelope(
    snapshot: ReportSnapshot, narrative: ReportNarrative, digest: str
) -> dict[str, object]:
    """What ``metric_snapshot`` holds: the numbers and, beside them, the narrative."""
    return {
        "snapshot": snapshot.model_dump(mode="json"),
        "narrative": narrative.model_dump(mode="json"),
        "data_hash": digest,
    }


def open_envelope(revision: ReportRevision) -> StoredReport:
    document = revision.metric_snapshot
    return StoredReport(
        revision=revision,
        snapshot=ReportSnapshot.model_validate(document["snapshot"]),
        narrative=ReportNarrative.model_validate(document["narrative"]),
        data_hash=str(document["data_hash"]),
    )


def snapshot_hash(
    organization_id: UUID,
    definition_id: UUID,
    month: date,
    revision: int,
    digest: str,
    narrative: ReportNarrative,
) -> str:
    """Globally unique: tenant, definition, month, revision, the numbers and the narrative."""
    return hashlib.sha256(
        canonical_json(
            {
                "organization_id": str(organization_id),
                "definition_id": str(definition_id),
                "month": month.isoformat(),
                "revision": revision,
                "data": digest,
                "narrative": narrative.model_dump(mode="json"),
            }
        ).encode()
    ).hexdigest()


def status_of(revision: ReportRevision, delivery: ReportDelivery | None) -> ReportStatus:
    if revision.status != REVISION_APPROVED:
        return ReportStatus.DRAFT
    return ReportStatus.SENT if delivery else ReportStatus.READY


class ReportService:
    def __init__(self, audit: AuditEventService | None = None) -> None:
        self.audit = audit or AuditEventService()

    async def _record(
        self,
        session: AsyncSession,
        *,
        event: str,
        organization_id: UUID,
        actor_id: UUID | None,
        revision: ReportRevision,
        correlation_id: str,
        summary: str,
        metadata: dict[str, object],
        result: AuditResult = AuditResult.SUCCEEDED,
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=result,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.WORKFLOW,
                actor_id=actor_id,
                organization_id=organization_id,
                product_key=AUDIT_PRODUCT,
                resource_type="report_revision",
                resource_id=revision.id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    async def ensure_definition(
        self, session: AsyncSession, organization_id: UUID
    ) -> ReportDefinition:
        """The organization's one monthly report definition, created on first use."""
        definition = await session.scalar(
            select(ReportDefinition)
            .where(
                ReportDefinition.organization_id == organization_id,
                ReportDefinition.key == DEFINITION_KEY,
            )
            .with_for_update()
        )
        if definition is not None:
            return definition
        try:
            # A concurrent first use loses to the unique key and finds the winner's row.
            async with session.begin_nested():
                definition = ReportDefinition(
                    organization_id=organization_id,
                    key=DEFINITION_KEY,
                    name="Monthly performance report",
                    requested_scope={"scope": "organization", "locations": "active"},
                    metric_references=[],
                    status="active",
                    version=1,
                )
                session.add(definition)
                await session.flush()
        except IntegrityError:
            definition = await session.scalar(
                select(ReportDefinition)
                .where(
                    ReportDefinition.organization_id == organization_id,
                    ReportDefinition.key == DEFINITION_KEY,
                )
                .with_for_update()
            )
            assert definition is not None
        return definition

    async def _revisions(
        self, session: AsyncSession, organization_id: UUID, month: date
    ) -> list[ReportRevision]:
        rows = await session.scalars(
            select(ReportRevision)
            .where(
                ReportRevision.organization_id == organization_id,
                ReportRevision.period_month == month,
            )
            .order_by(ReportRevision.revision)
        )
        return list(rows)

    async def get(
        self,
        session: AsyncSession,
        organization_id: UUID,
        month: date,
        revision: int,
        *,
        lock: bool = False,
    ) -> StoredReport:
        statement = select(ReportRevision).where(
            ReportRevision.organization_id == organization_id,
            ReportRevision.period_month == month,
            ReportRevision.revision == revision,
        )
        row = await session.scalar(statement.with_for_update() if lock else statement)
        if row is None:
            raise ReportNotFoundError
        return open_envelope(row)

    async def latest(
        self, session: AsyncSession, organization_id: UUID, month: date
    ) -> StoredReport | None:
        revisions = await self._revisions(session, organization_id, month)
        return open_envelope(revisions[-1]) if revisions else None

    async def revision_count(
        self, session: AsyncSession, organization_id: UUID, month: date
    ) -> int:
        return int(
            await session.scalar(
                select(func.count(ReportRevision.id)).where(
                    ReportRevision.organization_id == organization_id,
                    ReportRevision.period_month == month,
                )
            )
            or 0
        )

    async def delivery(
        self, session: AsyncSession, organization_id: UUID, revision_id: UUID
    ) -> ReportDelivery | None:
        found: ReportDelivery | None = await session.scalar(
            select(ReportDelivery).where(
                ReportDelivery.organization_id == organization_id,
                ReportDelivery.report_revision_id == revision_id,
            )
        )
        return found

    async def generate(
        self,
        session: AsyncSession,
        organization_id: UUID,
        month: date,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        now: datetime | None = None,
    ) -> tuple[StoredReport, bool]:
        """Compute the month and store it. Returns the revision and whether it is new.

        Identical data returns the existing draft. After approval an identical regeneration is
        refused; different data becomes a new draft and the approved revision is untouched.
        """
        now = now or datetime.now(UTC)
        require_ended(month, now)
        # The definition row is the lock that numbers revisions: one generation at a time.
        definition = await self.ensure_definition(session, organization_id)
        snapshot = await build_snapshot(session, organization_id, month, now=now)
        digest = data_hash(snapshot)
        previous = await self.latest(session, organization_id, month)
        narrative = ReportNarrative()
        if previous is not None:
            if previous.data_hash == digest:
                if previous.is_approved:
                    raise ReportAlreadyApprovedError
                return previous, False
            # A drafted narrative was checked against the old numbers, so it is not carried
            # over; a person's own words are.
            if previous.narrative.origin is NarrativeOrigin.MANUAL:
                narrative = previous.narrative
        number = previous.revision.revision + 1 if previous else 1
        revision = ReportRevision(
            organization_id=organization_id,
            report_definition_id=definition.id,
            period_month=month,
            revision=number,
            snapshot_hash=snapshot_hash(
                organization_id, definition.id, month, number, digest, narrative
            ),
            metric_snapshot=envelope(snapshot, narrative, digest),
            metric_versions=list(METRIC_VERSIONS),
            limitations=sorted({note.code.value for note in snapshot.notes}),
            status=REVISION_DRAFT,
            created_at=now,
        )
        session.add(revision)
        await session.flush()
        await self._record(
            session,
            event="reports.report.generated",
            organization_id=organization_id,
            actor_id=actor_id,
            revision=revision,
            correlation_id=correlation_id,
            summary="Monthly report generated.",
            metadata={
                "month": month.isoformat(),
                "revision": number,
                "readiness": snapshot.readiness.value,
                "data_hash": digest,
            },
        )
        return open_envelope(revision), True

    async def assert_editable(
        self, session: AsyncSession, organization_id: UUID, stored: StoredReport
    ) -> None:
        """Only the newest revision of a month, and only while it is a draft, can be edited."""
        if stored.is_approved:
            raise ReportNotEditableError
        count = await self.revision_count(session, organization_id, stored.month)
        if stored.revision.revision != count:
            raise ReportRevisionSupersededError

    async def _editable(
        self, session: AsyncSession, organization_id: UUID, month: date, revision: int
    ) -> StoredReport:
        stored = await self.get(session, organization_id, month, revision, lock=True)
        await self.assert_editable(session, organization_id, stored)
        return stored

    async def set_narrative(
        self,
        session: AsyncSession,
        organization_id: UUID,
        month: date,
        revision: int,
        narrative: ReportNarrative,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        event: str = "reports.narrative.edited",
    ) -> StoredReport:
        """Replace a draft's narrative; the revision's hash follows its content."""
        stored = await self._editable(session, organization_id, month, revision)
        row = stored.revision
        row.metric_snapshot = envelope(stored.snapshot, narrative, stored.data_hash)
        row.snapshot_hash = snapshot_hash(
            organization_id,
            row.report_definition_id,
            month,
            row.revision,
            stored.data_hash,
            narrative,
        )
        await session.flush()
        await self._record(
            session,
            event=event,
            organization_id=organization_id,
            actor_id=actor_id,
            revision=row,
            correlation_id=correlation_id,
            summary="Report narrative updated.",
            metadata={
                "month": month.isoformat(),
                "revision": row.revision,
                "origin": narrative.origin.value,
            },
        )
        return open_envelope(row)

    async def approve(
        self,
        session: AsyncSession,
        organization_id: UUID,
        month: date,
        revision: int,
        *,
        actor_id: UUID,
        correlation_id: str,
        now: datetime | None = None,
    ) -> tuple[StoredReport, bool]:
        """Approve the current draft. Approving it again is a no-op that returns it."""
        stored = await self.get(session, organization_id, month, revision, lock=True)
        if stored.is_approved:
            return stored, False
        if stored.revision.revision != (await self.revision_count(session, organization_id, month)):
            raise ReportRevisionSupersededError
        if stored.snapshot.readiness is ReportReadiness.MISSING_DATA:
            raise ReportDataMissingError
        if stored.narrative.is_empty:
            raise ReportNarrativeEmptyError
        row = stored.revision
        row.status = REVISION_APPROVED
        row.approved_by_user_id = actor_id
        row.approved_at = now or datetime.now(UTC)
        await session.flush()
        await self._record(
            session,
            event="reports.report.approved",
            organization_id=organization_id,
            actor_id=actor_id,
            revision=row,
            correlation_id=correlation_id,
            summary="Monthly report approved.",
            metadata={
                "month": month.isoformat(),
                "revision": row.revision,
                "readiness": stored.snapshot.readiness.value,
                "data_hash": stored.data_hash,
            },
        )
        return open_envelope(row), True

    async def mark_sent(
        self,
        session: AsyncSession,
        organization_id: UUID,
        month: date,
        revision: int,
        sent_on: date,
        *,
        actor_id: UUID,
        correlation_id: str,
        now: datetime | None = None,
    ) -> tuple[ReportDelivery, bool]:
        """Record that a person sent the approved report. The same revision is recorded once."""
        now = now or datetime.now(UTC)
        stored = await self.get(session, organization_id, month, revision, lock=True)
        if not stored.is_approved:
            raise ReportNotApprovedError
        existing = await self.delivery(session, organization_id, stored.revision.id)
        if existing is not None:
            return existing, False
        following = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
        if sent_on < following or sent_on > report_today(now):
            raise ReportSentDateInvalidError
        delivery = ReportDelivery(
            organization_id=organization_id,
            report_revision_id=stored.revision.id,
            idempotency_key=f"{organization_id}:{month.isoformat()}:{stored.revision.revision}",
            status=DELIVERY_SENT,
            sent_on=sent_on,
            sent_by_user_id=actor_id,
        )
        session.add(delivery)
        await session.flush()
        await self._record(
            session,
            event="reports.report.sent",
            organization_id=organization_id,
            actor_id=actor_id,
            revision=stored.revision,
            correlation_id=correlation_id,
            summary="Monthly report recorded as sent.",
            metadata={
                "month": month.isoformat(),
                "revision": stored.revision.revision,
                "sent_on": sent_on.isoformat(),
            },
        )
        return delivery, True
