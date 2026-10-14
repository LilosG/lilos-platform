"""Persistence of the monthly report: idempotent generation, hashes, immutability, sending."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.insights.models import ReportDefinition, ReportDelivery, ReportRevision
from apps.api.app.reports.contracts import (
    NarrativeOrigin,
    ReportNarrative,
    ReportReadiness,
    ReportStatus,
)
from apps.api.app.reports.errors import (
    ReportAlreadyApprovedError,
    ReportDataMissingError,
    ReportNarrativeEmptyError,
    ReportNotApprovedError,
    ReportNotEditableError,
    ReportRevisionSupersededError,
    ReportSentDateInvalidError,
)
from apps.api.app.reports.service import ReportService, status_of
from reports.support import (
    OCTOBER_FIRST,
    SEPTEMBER,
    Factory,
    seed_complete_month,
    seed_org,
    store_metrics,
)

pytestmark = pytest.mark.integration
SENT = datetime(2026, 10, 5, 18, 0, tzinfo=UTC)
WORDS = ReportNarrative(
    what_changed="Profile views grew.", next_work="Keep posting.", origin=NarrativeOrigin.MANUAL
)


async def user(factory: Factory) -> UUID:
    async with factory.begin() as session:
        profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
        session.add(profile)
        await session.flush()
        return profile.id


async def generate(factory: Factory, org: UUID, svc: ReportService | None = None):  # type: ignore[no-untyped-def]
    async with factory.begin() as session:
        return await (svc or ReportService()).generate(
            session, org, SEPTEMBER, actor_id=None, correlation_id="test", now=OCTOBER_FIRST
        )


async def events(factory: Factory, org: UUID) -> list[str]:
    async with factory() as session:
        rows = await session.scalars(
            select(AuditEvent.event_type)
            .where(AuditEvent.organization_id == org, AuditEvent.event_type.like("reports.%"))
            .order_by(AuditEvent.occurred_at)
        )
        return list(rows)


@pytest.mark.anyio
async def test_one_definition_per_organization_and_identical_data_returns_the_same_revision(
    factory: Factory,
) -> None:
    org, gbp, location = await seed_org(factory)
    await seed_complete_month(factory, org, gbp, location)

    first, created = await generate(factory, org)
    again, created_again = await generate(factory, org)

    assert created and not created_again
    assert again.revision.id == first.revision.id and first.revision.revision == 1
    assert first.revision.period_month == SEPTEMBER and first.revision.status == "draft"
    assert first.snapshot.readiness is ReportReadiness.READY
    async with factory() as session:
        definitions = await session.scalar(
            select(func.count(ReportDefinition.id)).where(ReportDefinition.organization_id == org)
        )
        revisions = await session.scalar(
            select(func.count(ReportRevision.id)).where(ReportRevision.organization_id == org)
        )
    assert (definitions, revisions) == (1, 1)
    assert first.revision.limitations == [] and first.revision.metric_versions


@pytest.mark.anyio
async def test_two_tenants_with_identical_data_never_share_a_hash(factory: Factory) -> None:
    hashes: list[str] = []
    data_hashes: set[str] = set()
    for name in ("Alpha", "Bravo"):
        org, gbp, _ = await seed_org(factory, name)
        await store_metrics(factory, org, gbp, SEPTEMBER, 5)
        stored, _ = await generate(factory, org)
        hashes.append(stored.revision.snapshot_hash)
        data_hashes.add(stored.data_hash)

    assert hashes[0] != hashes[1]
    assert len(data_hashes) == 1  # the numbers are identical; only the tenant differs
    assert all(len(value) == 64 for value in hashes)


@pytest.mark.anyio
async def test_changed_data_is_the_next_revision_and_a_draft_edit_recomputes_the_hash(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5, skip_days=[date(2026, 9, 30)])
    svc = ReportService()
    first, _ = await generate(factory, org, svc)
    assert first.snapshot.readiness is ReportReadiness.READY_WITH_NOTE

    async with factory.begin() as session:  # Google's late data arrives
        from apps.api.app.products.gbp.performance_models import GBPPerformanceDailyMetric
        from reports.support import days_of

        run = await session.scalar(select(ReportRevision.id).limit(0))
        assert run is None
        source = (
            await session.execute(
                select(
                    GBPPerformanceDailyMetric.gbp_location_id,
                    GBPPerformanceDailyMetric.sync_run_id,
                ).limit(1)
            )
        ).one()
        for metric in {
            row
            for row in await session.scalars(select(GBPPerformanceDailyMetric.metric).distinct())
        }:
            session.add(
                GBPPerformanceDailyMetric(
                    organization_id=org,
                    gbp_location_id=source[0],
                    metric=metric,
                    metric_date=days_of(SEPTEMBER)[-1],
                    value=5,
                    sync_run_id=source[1],
                )
            )
    second, created = await generate(factory, org, svc)

    assert created and second.revision.revision == 2
    assert second.revision.snapshot_hash != first.revision.snapshot_hash
    assert second.data_hash != first.data_hash

    before = second.revision.snapshot_hash
    async with factory.begin() as session:
        edited = await svc.set_narrative(
            session, org, SEPTEMBER, 2, WORDS, actor_id=None, correlation_id="edit"
        )
    assert edited.revision.snapshot_hash != before
    assert edited.narrative == WORDS and edited.data_hash == second.data_hash

    # Regenerating keeps a person's own words, and not a draft that was checked against old numbers.
    async with factory.begin() as session:
        stored = await svc.get(session, org, SEPTEMBER, 2, lock=True)
        document = dict(stored.revision.metric_snapshot)
        document["narrative"] = {**stored.narrative.model_dump(mode="json"), "origin": "hermes"}
        stored.revision.metric_snapshot = document
    async with factory.begin() as session:
        from apps.api.app.products.gbp.performance_models import GBPPerformanceDailyMetric

        await session.execute(
            text(
                "update gbp_performance_daily_metrics set value = 7 "
                "where metric_date = '2026-09-01'"
            )
        )
    third, _ = await generate(factory, org, svc)
    assert third.revision.revision == 3 and third.narrative.is_empty


@pytest.mark.anyio
async def test_an_approved_revision_is_immutable_and_a_changed_regeneration_is_a_new_draft(
    factory: Factory,
) -> None:
    org, gbp, location = await seed_org(factory)
    await seed_complete_month(factory, org, gbp, location)
    svc, approver = ReportService(), await user(factory)
    await generate(factory, org, svc)
    async with factory.begin() as session:
        await svc.set_narrative(
            session, org, SEPTEMBER, 1, WORDS, actor_id=approver, correlation_id="c"
        )
    async with factory.begin() as session:
        approved, changed = await svc.approve(
            session, org, SEPTEMBER, 1, actor_id=approver, correlation_id="c"
        )
    assert changed and approved.revision.status == "approved"
    assert approved.revision.approved_by_user_id == approver and approved.revision.approved_at

    async with factory.begin() as session:
        with pytest.raises(ReportNotEditableError):
            await svc.set_narrative(
                session, org, SEPTEMBER, 1, WORDS, actor_id=approver, correlation_id="c"
            )
    with pytest.raises(ReportAlreadyApprovedError):
        await generate(factory, org, svc)  # nothing changed

    # The database itself refuses any change to an approved revision.
    with pytest.raises(DBAPIError):
        async with factory.begin() as session:
            await session.execute(
                text(
                    "update report_revisions set limitations = '[\"x\"]'::jsonb "
                    "where status = 'approved'"
                )
            )
    # Approving again is a no-op.
    async with factory.begin() as session:
        again, changed = await svc.approve(
            session, org, SEPTEMBER, 1, actor_id=approver, correlation_id="c"
        )
    assert not changed and again.revision.approved_at == approved.revision.approved_at

    async with factory.begin() as session:  # the data moves on
        await session.execute(
            text(
                "update gbp_performance_daily_metrics set value = 9 "
                "where metric_date = '2026-09-02'"
            )
        )
    newer, created = await generate(factory, org, svc)
    assert created and newer.revision.revision == 2 and newer.revision.status == "draft"
    async with factory() as session:
        first = await svc.get(session, org, SEPTEMBER, 1)
    assert first.revision.status == "approved" and first.narrative == WORDS
    assert first.data_hash != newer.data_hash

    async with factory.begin() as session:  # the older revision can no longer be approved or edited
        with pytest.raises(ReportNotEditableError):
            await svc.set_narrative(
                session, org, SEPTEMBER, 1, WORDS, actor_id=None, correlation_id="c"
            )


@pytest.mark.anyio
async def test_approval_is_refused_for_missing_data_an_empty_narrative_and_an_old_revision(
    factory: Factory,
) -> None:
    org, gbp, location = await seed_org(factory)
    approver, svc = await user(factory), ReportService()

    missing, _ = await generate(factory, org, svc)  # nothing synced for the month
    assert missing.snapshot.readiness is ReportReadiness.MISSING_DATA
    async with factory.begin() as session:
        await svc.set_narrative(
            session, org, SEPTEMBER, 1, WORDS, actor_id=None, correlation_id="c"
        )
    async with factory.begin() as session:
        with pytest.raises(ReportDataMissingError):
            await svc.approve(session, org, SEPTEMBER, 1, actor_id=approver, correlation_id="c")

    async with factory.begin() as session:  # the person clears it again
        await svc.set_narrative(
            session,
            org,
            SEPTEMBER,
            1,
            ReportNarrative(origin=NarrativeOrigin.MANUAL),
            actor_id=None,
            correlation_id="c",
        )
    await seed_complete_month(factory, org, gbp, location)
    ready, created = await generate(factory, org, svc)
    assert created and ready.revision.revision == 2
    async with factory.begin() as session:
        with pytest.raises(ReportNarrativeEmptyError):
            await svc.approve(session, org, SEPTEMBER, 2, actor_id=approver, correlation_id="c")
    async with factory.begin() as session:
        with pytest.raises(ReportRevisionSupersededError):
            await svc.approve(session, org, SEPTEMBER, 1, actor_id=approver, correlation_id="c")


@pytest.mark.anyio
async def test_marking_as_sent_is_recorded_once_by_a_person_and_audited(factory: Factory) -> None:
    org, gbp, location = await seed_org(factory)
    await seed_complete_month(factory, org, gbp, location)
    svc, person = ReportService(), await user(factory)
    await generate(factory, org, svc)
    async with factory.begin() as session:
        with pytest.raises(ReportNotApprovedError):
            await svc.mark_sent(
                session,
                org,
                SEPTEMBER,
                1,
                date(2026, 10, 3),
                actor_id=person,
                correlation_id="c",
                now=SENT,
            )
    async with factory.begin() as session:
        await svc.set_narrative(
            session, org, SEPTEMBER, 1, WORDS, actor_id=person, correlation_id="c"
        )
    async with factory.begin() as session:
        await svc.approve(session, org, SEPTEMBER, 1, actor_id=person, correlation_id="c")

    for bad in (date(2026, 9, 30), SENT.date() + timedelta(days=1)):
        async with factory.begin() as session:
            with pytest.raises(ReportSentDateInvalidError):
                await svc.mark_sent(
                    session, org, SEPTEMBER, 1, bad, actor_id=person, correlation_id="c", now=SENT
                )

    async with factory.begin() as session:
        delivery, created = await svc.mark_sent(
            session,
            org,
            SEPTEMBER,
            1,
            date(2026, 10, 3),
            actor_id=person,
            correlation_id="c",
            now=SENT,
        )
    assert created and delivery.sent_on == date(2026, 10, 3) and delivery.status == "sent"
    assert delivery.sent_by_user_id == person
    assert delivery.idempotency_key == f"{org}:2026-09-01:1"
    assert delivery.notification_delivery_id is None  # nothing was emailed or notified

    async with factory.begin() as session:
        replay, created = await svc.mark_sent(
            session,
            org,
            SEPTEMBER,
            1,
            date(2026, 10, 4),
            actor_id=person,
            correlation_id="c",
            now=SENT,
        )
    assert not created and replay.id == delivery.id and replay.sent_on == date(2026, 10, 3)
    async with factory() as session:
        count = await session.scalar(
            select(func.count(ReportDelivery.id)).where(ReportDelivery.organization_id == org)
        )
        revision = (await svc.get(session, org, SEPTEMBER, 1)).revision
        assert status_of(revision, delivery) is ReportStatus.SENT
    assert count == 1
    assert await events(factory, org) == [
        "reports.report.generated",
        "reports.narrative.edited",
        "reports.report.approved",
        "reports.report.sent",
    ]
