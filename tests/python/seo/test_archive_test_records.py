"""scripts.archive_test_records: closes exactly the listed records, audited, and only once."""

import asyncio
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.audit.models import AuditEvent
from apps.api.app.growth.models import GrowthAction, GrowthInitiative
from scripts import archive_test_records as script

from .test_command_center_opportunities import seed
from .test_seo_api import seo_client

__all__ = ["seo_client"]


def test_dry_run_changes_nothing_and_apply_cancels_the_plan_once_with_audit(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, ids = seo_client
    seeded = asyncio.run(seed(seo_session_factory, ids))
    other = seeded["growth"]
    record = script.ArchiveRecord(
        kind="growth_initiative", id=other, organization="Test", description="Diagnostic"
    )
    missing = script.ArchiveRecord(
        kind="growth_initiative",
        id=UUID(int=1),
        organization="Test",
        description="Not there",
    )

    def run(*, apply: bool) -> list[script.Outcome]:
        return asyncio.run(
            script.archive_test_records(seo_session_factory, apply=apply, records=(record, missing))
        )

    async def state() -> tuple[str, list[str], int]:
        async with seo_session_factory() as session:
            plan = await session.get(GrowthInitiative, other)
            assert plan is not None
            actions = list(
                await session.scalars(
                    select(GrowthAction.status).where(GrowthAction.initiative_id == other)
                )
            )
            audits = await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.resource_id == other, AuditEvent.event_type.like("growth.%"))
            )
            return plan.status, actions, int(audits or 0)

    dry = run(apply=False)
    assert [o.result for o in dry] == ["archive", "not_found"]
    assert asyncio.run(state()) == ("proposed", ["proposed"], 0)
    applied = run(apply=True)
    assert [o.result for o in applied] == ["archive", "not_found"]
    status, actions, audits = asyncio.run(state())
    assert (status, actions) == ("cancelled", ["cancelled"])
    assert audits == 1
    # Idempotent: a second run finds it closed and writes nothing more.
    again = run(apply=True)
    assert [o.result for o in again] == ["already_closed", "not_found"]
    assert asyncio.run(state()) == ("cancelled", ["cancelled"], 1)


def test_only_the_listed_production_record_is_targeted() -> None:
    assert [(r.kind, str(r.id)) for r in script.TEST_RECORDS] == [
        ("growth_initiative", "4b8fdf4d-fa06-4316-bf3b-c28182afe35a")
    ]
