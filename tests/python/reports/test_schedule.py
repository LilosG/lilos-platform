"""The monthly report job: scheduled at 8 AM Pacific on the 1st, once per client per month."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, update

from apps.api.app.execution.automations import FAILURE_POLICY, AutomationReason
from apps.api.app.execution.models import Schedule, WorkflowDefinition, WorkflowVersion
from apps.api.app.execution.service import ExecutionService
from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES, is_tenant_workflow_key
from apps.api.app.insights.models import ReportRevision
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.reports import workflow as report_workflow
from apps.api.app.reports.contracts import NoteCode, ReportReadiness
from apps.api.app.reports.schedule import (
    REPORT_CRON,
    REPORT_SCHEDULE_KEY,
    REPORT_TIMEZONE_NAME,
    REPORT_WORKFLOW_KEY,
)
from apps.api.app.reports.service import ReportService
from reports.support import (
    SEPTEMBER,
    Factory,
    add_location,
    seed_complete_month,
    seed_org,
    set_location_status,
    store_metrics,
)
from scripts.ensure_client_schedules import Action, ensure_client_schedules

pytestmark = pytest.mark.integration
OCTOBER_FIRST = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)  # 8:00 AM Pacific
SCHEDULED = {"scheduled_for": OCTOBER_FIRST.isoformat()}


@pytest.fixture(autouse=True)
def the_job_runs_on_october_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report_workflow, "utc_now", lambda: OCTOBER_FIRST + timedelta(minutes=2))


async def run_job(factory: Factory, org: UUID, document: dict[str, Any] | None = None):  # type: ignore[no-untyped-def]
    async with factory.begin() as session:
        return await report_workflow.handle_monthly_report_generation(
            session,
            organization_id=org,
            location_id=None,
            input_document=SCHEDULED if document is None else document,
            correlation_id="monthly-report-test",
            workflow_run_id=UUID(int=1),
        )


async def revisions(factory: Factory, org: UUID) -> list[tuple[Any, int, str]]:
    async with factory() as session:
        rows = await session.execute(
            select(ReportRevision.period_month, ReportRevision.revision, ReportRevision.status)
            .where(ReportRevision.organization_id == org)
            .order_by(ReportRevision.period_month, ReportRevision.revision)
        )
        return [tuple(row) for row in rows]


def test_the_workflow_is_known_and_a_failure_to_generate_needs_attention() -> None:
    assert REPORT_WORKFLOW_KEY in WORKFLOW_TYPES and is_tenant_workflow_key(REPORT_WORKFLOW_KEY)
    assert AutomationReason.REPORT_GENERATION_FAILED in FAILURE_POLICY


@pytest.mark.anyio
async def test_every_active_client_gets_one_schedule_at_8am_pacific_on_the_1st(
    factory: Factory,
) -> None:
    active, _, _ = await seed_org(factory, "Active")
    archived, _, _ = await seed_org(factory, "Archived")
    async with factory.begin() as session:
        await session.execute(
            update(Organization)
            .where(Organization.id == archived)
            .values(status=OrganizationStatus.ARCHIVED, archived_at=datetime.now(UTC))
        )
        await session.execute(
            update(Organization).where(Organization.id == active).values(timezone="Europe/Paris")
        )
    now = datetime(2026, 10, 14, 19, 0, tzinfo=UTC)

    dry = await ensure_client_schedules(factory, apply=False, now=now)
    assert not dry.applied
    async with factory() as session:
        assert await session.scalar(select(func.count(Schedule.id))) == 0

    applied = await ensure_client_schedules(factory, apply=True, now=now)
    reports = [c for c in applied.changes if c.wanted.workflow_key == REPORT_WORKFLOW_KEY]
    assert [c.organization_id for c in reports] == [active] and reports[0].action is Action.CREATE

    async with factory() as session:
        rows = list(
            await session.scalars(select(Schedule).where(Schedule.key == REPORT_SCHEDULE_KEY))
        )
    assert len(rows) == 1
    schedule = rows[0]
    # Pacific time whatever the client's own timezone, on the 1st at 8:00 AM.
    assert (schedule.organization_id, schedule.cron_expression) == (active, REPORT_CRON)
    assert schedule.timezone == REPORT_TIMEZONE_NAME and schedule.location_id is None
    expected = datetime(2026, 11, 1, 8, tzinfo=ZoneInfo(REPORT_TIMEZONE_NAME)).astimezone(UTC)
    assert schedule.next_run_at == expected and schedule.status == "active"

    again = await ensure_client_schedules(factory, apply=True, now=now)
    assert {c.action for c in again.changes if c.wanted.workflow_key == REPORT_WORKFLOW_KEY} == {
        Action.UNCHANGED
    }
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count(Schedule.id)).where(Schedule.key == REPORT_SCHEDULE_KEY)
            )
            == 1
        )


@pytest.mark.anyio
async def test_the_scheduler_dispatches_it_and_never_for_an_archived_client(
    factory: Factory,
) -> None:
    active, _, _ = await seed_org(factory, "Active")
    archived, _, _ = await seed_org(factory, "Archived")
    await ensure_client_schedules(factory, apply=True, now=datetime(2026, 10, 14, tzinfo=UTC))
    async with factory.begin() as session:
        await session.execute(
            update(Organization)
            .where(Organization.id == archived)
            .values(status=OrganizationStatus.ARCHIVED, archived_at=datetime.now(UTC))
        )
        await session.execute(
            update(Schedule)
            .where(Schedule.key == REPORT_SCHEDULE_KEY)
            .values(next_run_at=OCTOBER_FIRST)
        )
        # Every other recurring job is days away, so only the report can be due.
        await session.execute(
            update(Schedule)
            .where(Schedule.key != REPORT_SCHEDULE_KEY)
            .values(next_run_at=datetime(2030, 1, 1, tzinfo=UTC))
        )

    async with factory.begin() as session:
        service = ExecutionService()
        first = await service.dispatch_due_schedule(session, "reports-test")
        second = await service.dispatch_due_schedule(session, "reports-test")
        assert first is not None and second is None  # the archived client's schedule never runs
        assert first.organization_id == active
        version = await session.get(WorkflowVersion, first.workflow_version_id)
        assert version is not None
        key = await session.scalar(
            select(WorkflowDefinition.key).where(WorkflowDefinition.id == version.definition_id)
        )
        assert key == REPORT_WORKFLOW_KEY
        document = dict(first.input_document)
        schedule = await session.get(Schedule, UUID(str(document["schedule_id"])))
        assert schedule is not None and schedule.next_run_at > OCTOBER_FIRST
    # The run it created hands the job the moment the schedule fired.
    outcome = await run_job(factory, active, document)
    assert outcome.result == "succeeded"
    assert outcome.result_reference == "report:2026-09-01:1:created"


@pytest.mark.anyio
async def test_the_job_writes_one_draft_per_client_per_month_and_a_rerun_changes_nothing(
    factory: Factory,
) -> None:
    first, gbp, location = await seed_org(factory, "First")
    second, second_gbp, second_location = await seed_org(factory, "Second")
    await seed_complete_month(factory, first, gbp, location)
    await seed_complete_month(factory, second, second_gbp, second_location)

    one = await run_job(factory, first)
    two = await run_job(factory, second)
    rerun = await run_job(factory, first)

    assert one.result == two.result == rerun.result == "succeeded"
    assert one.result_reference == "report:2026-09-01:1:created"
    assert rerun.result_reference == "report:2026-09-01:1:existing"
    assert await revisions(factory, first) == [(SEPTEMBER, 1, "draft")]
    assert await revisions(factory, second) == [(SEPTEMBER, 1, "draft")]


@pytest.mark.anyio
async def test_a_month_google_has_not_finished_is_a_draft_with_a_note_that_can_be_regenerated(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory, "Lagging")
    lagging_day = datetime(2026, 9, 30).date()
    await store_metrics(factory, org, gbp, SEPTEMBER, 5, skip_days=[lagging_day])

    outcome = await run_job(factory, org)

    assert outcome.result == "succeeded"
    async with factory() as session:
        stored = await ReportService().get(session, org, SEPTEMBER, 1)
    assert stored.snapshot.readiness is ReportReadiness.READY_WITH_NOTE
    assert NoteCode.GBP_MONTH_PARTIAL in {n.code for n in stored.snapshot.notes}
    # The last day arrives; a person regenerates before approving and gets the next revision.
    await store_metrics(
        factory,
        org,
        gbp,
        SEPTEMBER,
        5,
        skip_days=[
            d
            for d in __import__("reports.support", fromlist=["days_of"]).days_of(SEPTEMBER)
            if d != lagging_day
        ],
    )
    async with factory.begin() as session:
        regenerated, created = await ReportService().generate(
            session,
            org,
            SEPTEMBER,
            actor_id=None,
            correlation_id="regen",
            now=OCTOBER_FIRST + timedelta(days=2),
        )
    assert created and regenerated.revision.revision == 2


@pytest.mark.anyio
async def test_clients_and_locations_that_no_longer_run_are_skipped(factory: Factory) -> None:
    paused, paused_gbp, _ = await seed_org(factory, "PausedClient")
    archived, archived_gbp, _ = await seed_org(factory, "ArchivedClient")
    dormant, dormant_gbp, dormant_location = await seed_org(factory, "AllRetired")
    mixed, mixed_gbp, mixed_location = await seed_org(factory, "Mixed")
    for org, gbp in (
        (paused, paused_gbp),
        (archived, archived_gbp),
        (dormant, dormant_gbp),
        (mixed, mixed_gbp),
    ):
        await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    retired_gbp = (await add_location(factory, mixed, "Old", status=LocationStatus.ARCHIVED))[1]
    assert retired_gbp
    await store_metrics(factory, mixed, retired_gbp, SEPTEMBER, 500)
    async with factory.begin() as session:
        await session.execute(
            update(Organization)
            .where(Organization.id == paused)
            .values(status=OrganizationStatus.PAUSED)
        )
        await session.execute(
            update(Organization)
            .where(Organization.id == archived)
            .values(status=OrganizationStatus.ARCHIVED, archived_at=datetime.now(UTC))
        )
    for status in (LocationStatus.PAUSED,):
        await set_location_status(factory, dormant, dormant_location, status)

    results = {
        name: await run_job(factory, org)
        for name, org in (
            ("paused", paused),
            ("archived", archived),
            ("dormant", dormant),
            ("mixed", mixed),
        )
    }

    for name in ("paused", "archived", "dormant"):
        assert results[name].result_reference == "report-skipped:not-reportable", name
        assert (
            await revisions(
                factory,
                locals()[{"paused": "paused", "archived": "archived", "dormant": "dormant"}[name]],
            )
            == []
        )
    assert results["mixed"].result_reference == "report:2026-09-01:1:created"
    async with factory() as session:
        stored = await ReportService().get(session, mixed, SEPTEMBER, 1)
    # Only the active location counts; the archived profile's 500s never reach the report.
    assert stored.snapshot.gbp.profile_views.total.current.value == 30 * 4 * 5
    assert stored.snapshot.gbp.locations == []


@pytest.mark.anyio
async def test_an_approved_report_is_not_redrafted_and_a_failure_is_retried(
    factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reports.test_service import WORDS, user

    org, gbp, location = await seed_org(factory)
    await seed_complete_month(factory, org, gbp, location)
    person = await user(factory)
    await run_job(factory, org)
    svc = ReportService()
    async with factory.begin() as session:
        await svc.set_narrative(
            session, org, SEPTEMBER, 1, WORDS, actor_id=person, correlation_id="c"
        )
    async with factory.begin() as session:
        await svc.approve(session, org, SEPTEMBER, 1, actor_id=person, correlation_id="c")

    unchanged = await run_job(factory, org)
    assert unchanged.result == "succeeded"
    assert unchanged.result_reference == "report-unchanged:2026-09-01"
    assert await revisions(factory, org) == [(SEPTEMBER, 1, "approved")]

    async def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(ReportService, "generate", boom)
    failed = await run_job(factory, org)
    assert (failed.result, failed.safe_error) == ("retryable_failure", "REPORT_GENERATION_FAILED")
