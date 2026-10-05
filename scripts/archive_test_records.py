"""Archive the diagnostic and test records found in production Opportunities.

Production review of Opportunities found records that were created to test the platform, not
to serve a client (for example the Coco Maya growth plan "Diagnostic: test agent.content as
executor workflow key."). `TEST_RECORDS` lists exactly those ids and nothing else; every id
was matched by a read-only query and is listed in the pull request that added it.

Nothing is deleted. Each record is closed through the same service and status transition the
product uses (a Growth plan and its open actions are cancelled, a Content opportunity is
archived), with one audit event per row. It is idempotent: a record that is already closed or
no longer exists is reported and skipped, so a second run changes nothing.

Dry run by default: it prints exactly what `--apply` would do.

Run (Render shell):

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.archive_test_records
    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.archive_test_records --apply
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.growth.models import GrowthAction, GrowthInitiative
from apps.api.app.growth.service import (
    CANCELLABLE_ACTION_STATUSES,
    CANCELLABLE_INITIATIVE_STATUSES,
    GrowthService,
)
from apps.api.app.products.content.models import ContentOpportunity
from apps.api.app.products.content.service import ContentService
from scripts._cli import run_script

REASON_CODE = "test_record"
RETIRABLE_CONTENT_STATUSES = frozenset({"identified", "validated", "accepted"})

RecordKind = Literal["growth_initiative", "content_opportunity"]


@dataclass(frozen=True, slots=True)
class ArchiveRecord:
    kind: RecordKind
    id: UUID
    organization: str
    description: str


# Found by read-only queries against production on 2026-10-05; see the pull request.
TEST_RECORDS: tuple[ArchiveRecord, ...] = (
    ArchiveRecord(
        kind="growth_initiative",
        id=UUID("4b8fdf4d-fa06-4316-bf3b-c28182afe35a"),
        organization="Coco Maya",
        description="Diagnostic: test agent.content as executor workflow key.",
    ),
)


@dataclass(frozen=True, slots=True)
class Outcome:
    record: ArchiveRecord
    result: Literal["archive", "already_closed", "not_found"]
    from_status: str | None = None


async def _growth(
    session: AsyncSession,
    record: ArchiveRecord,
    growth: GrowthService,
    apply: bool,
    correlation: str,
) -> Outcome:
    initiative = await session.get(GrowthInitiative, record.id)
    if initiative is None:
        return Outcome(record, "not_found")
    if initiative.status not in CANCELLABLE_INITIATIVE_STATUSES:
        return Outcome(record, "already_closed", initiative.status)
    if apply:
        for action in await session.scalars(
            select(GrowthAction).where(
                GrowthAction.initiative_id == initiative.id,
                GrowthAction.organization_id == initiative.organization_id,
                GrowthAction.status.in_(CANCELLABLE_ACTION_STATUSES),
            )
        ):
            await growth.cancel_action(
                session, action, reason_code=REASON_CODE, correlation_id=correlation
            )
        await growth.cancel_initiative(
            session, initiative, reason_code=REASON_CODE, correlation_id=correlation
        )
    return Outcome(record, "archive", initiative.status)


async def _content(
    session: AsyncSession,
    record: ArchiveRecord,
    content: ContentService,
    apply: bool,
    correlation: str,
) -> Outcome:
    opportunity = await session.get(ContentOpportunity, record.id)
    if opportunity is None:
        return Outcome(record, "not_found")
    if opportunity.status not in RETIRABLE_CONTENT_STATUSES:
        return Outcome(record, "already_closed", opportunity.status)
    if apply:
        await content.retire_opportunity(
            session, opportunity, reason_code=REASON_CODE, correlation_id=correlation
        )
    return Outcome(record, "archive", opportunity.status)


async def archive_test_records(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    apply: bool,
    records: tuple[ArchiveRecord, ...] = TEST_RECORDS,
) -> list[Outcome]:
    growth, content = GrowthService(), ContentService()
    correlation = f"archive-test-records:{uuid4().hex[:12]}"
    outcomes: list[Outcome] = []
    for record in records:
        # One transaction per record: a failure leaves the others untouched.
        async with session_factory.begin() as session:
            outcomes.append(
                await _growth(session, record, growth, apply, correlation)
                if record.kind == "growth_initiative"
                else await _content(session, record, content, apply, correlation)
            )
    return outcomes


def format_report(outcomes: list[Outcome], *, applied: bool) -> list[str]:
    verb = "archived" if applied else "would archive"
    lines = []
    for outcome in outcomes:
        record = outcome.record
        label = f"{record.kind} {record.id} ({record.organization}: {record.description})"
        if outcome.result == "archive":
            lines.append(f"  {verb} {label} [was {outcome.from_status}]")
        elif outcome.result == "already_closed":
            lines.append(f"  SKIPPED {label}: already {outcome.from_status}")
        else:
            lines.append(f"  SKIPPED {label}: not found")
    changes = sum(o.result == "archive" for o in outcomes)
    lines.append(f"records={len(outcomes)} changes={changes}")
    return lines


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--apply", action="store_true", help="perform the changes (default: dry run)"
    )
    return parser.parse_args(argv)


async def main() -> int:
    args = _parse_args()
    runtime = create_database_runtime(Settings())
    try:
        outcomes = await archive_test_records(runtime.require_session_factory(), apply=args.apply)
        print("APPLIED" if args.apply else "DRY RUN (re-run with --apply to execute)")
        for line in format_report(outcomes, applied=args.apply):
            print(line)
        return 0
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    raise SystemExit(run_script("archive_test_records", main))
