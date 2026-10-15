"""The report-periods migration: backfill, the old-draft deletion, and the approved-row guard."""

import asyncio
import json
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from apps.api.app.database.model_registry import load_all_models
from apps.api.app.insights.models import ReportDefinition
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.reports.contracts import SNAPSHOT_SCHEMA_VERSION
from database.test_migrations import alembic_config

BEFORE = "20261014_0001"
pytestmark = pytest.mark.integration


def upgrade_error(config: Config) -> Exception | None:
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        return exc
    return None


async def seed_definition(url: str) -> tuple[UUID, UUID]:
    load_all_models()
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False).begin() as session:
            organization = Organization(
                name="Migrated",
                slug=f"migrated-{uuid4().hex[:6]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(organization)
            await session.flush()
            definition = ReportDefinition(
                organization_id=organization.id,
                key="monthly-performance",
                name="Monthly performance report",
                requested_scope={},
                metric_references=[],
                status="active",
                version=1,
            )
            session.add(definition)
            await session.flush()
            return organization.id, definition.id
    finally:
        await engine.dispose()


async def insert_old(
    url: str, org: UUID, definition: UUID, rows: list[tuple[date, int, str, int | None]]
) -> None:
    """Revisions in the one-month layout: (month, revision, status, snapshot schema version)."""
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            for month, number, status, version in rows:
                snapshot = (
                    {"snapshot": {"schema_version": version}} if version else {"snapshot": {}}
                )
                await connection.execute(
                    text(
                        "insert into report_revisions (id, organization_id, report_definition_id,"
                        " period_month, revision, snapshot_hash, metric_snapshot, metric_versions,"
                        " limitations, status, created_at) values (gen_random_uuid(), :org, :def,"
                        " :month, :rev, :hash, cast(:snap as jsonb), '[]', '[]', :status, :now)"
                    ),
                    {
                        "org": org,
                        "def": definition,
                        "month": month,
                        "rev": number,
                        "hash": uuid4().hex + uuid4().hex,
                        "snap": json.dumps(snapshot),
                        "status": status,
                        "now": datetime.now(UTC),
                    },
                )
    finally:
        await engine.dispose()


async def stored(url: str) -> list[tuple[date, date | None, str | None, int, str]]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            columns = {
                row[0]
                for row in await connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'report_revisions'"
                    )
                )
            }
            end = "period_end_month" if "period_end_month" in columns else "null"
            key = "comparison_key" if "comparison_key" in columns else "null"
            rows = await connection.execute(
                text(
                    f"select period_month, {end}, {key}, revision, status "
                    "from report_revisions order by period_month, revision"
                )
            )
            return [tuple(row) for row in rows]
    finally:
        await engine.dispose()


def fresh_database(config: Config) -> None:
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.mark.parametrize("run", [1])
def test_old_drafts_are_deleted_and_current_ones_backfilled_then_downgraded(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch, run: int
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = alembic_config()
    fresh_database(config)
    org, definition = asyncio.run(seed_definition(postgresql_test_url))
    command.downgrade(config, BEFORE)
    asyncio.run(
        insert_old(
            postgresql_test_url,
            org,
            definition,
            [
                (date(2026, 9, 1), 1, "draft", 1),  # the old snapshot schema: regenerable
                (date(2026, 8, 1), 2, "draft", None),  # no version at all counts as older
                (date(2026, 7, 1), 3, "draft", SNAPSHOT_SCHEMA_VERSION),
            ],
        )
    )

    command.upgrade(config, "head")

    assert asyncio.run(stored(postgresql_test_url)) == [
        (date(2026, 7, 1), date(2026, 7, 1), "previous", 3, "draft")
    ]
    # Revisions are now unique per period and comparison.
    engine = create_async_engine(postgresql_test_url, poolclass=NullPool)

    async def insert(end: date, key: str, number: int) -> None:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "insert into report_revisions (id, organization_id, report_definition_id,"
                    " period_month, period_end_month, comparison_key, revision, snapshot_hash,"
                    " metric_snapshot, metric_versions, limitations, status, created_at)"
                    " values (gen_random_uuid(), :org, :def, '2026-07-01', :end, :key, :rev, :hash,"
                    " '{}', '[]', '[]', 'draft', now())"
                ),
                {
                    "org": org,
                    "def": definition,
                    "end": end,
                    "key": key,
                    "rev": number,
                    "hash": uuid4().hex * 2,
                },
            )

    async def attempts() -> list[str]:
        refused: list[str] = []
        await insert(date(2026, 9, 1), "year_ago", 1)  # same start, another period: allowed
        await insert(date(2026, 7, 1), "year_ago", 1)  # another comparison: allowed
        await insert(date(2026, 7, 1), "baseline:2026-01:2026-03", 1)
        for end, key in (
            (date(2026, 7, 1), "previous"),  # a duplicate of revision 3
            (date(2026, 6, 1), "previous"),  # ends before it starts
            (date(2027, 7, 1), "previous"),  # 13 months
            (date(2026, 7, 1), "sometimes"),  # not a comparison key
            (date(2026, 7, 15), "previous"),  # not the first of a month
        ):
            try:
                await insert(end, key, 3)
            except IntegrityError:
                refused.append(f"{end}:{key}")
        return refused

    try:
        assert len(asyncio.run(attempts())) == 5
    finally:
        asyncio.run(engine.dispose())

    # Down again: what the single-month layout cannot hold is removed, the rest is kept.
    command.downgrade(config, BEFORE)
    assert asyncio.run(stored(postgresql_test_url)) == [(date(2026, 7, 1), None, None, 3, "draft")]
    command.upgrade(config, "head")
    fresh_database(config)


def test_an_approved_report_of_an_older_schema_stops_the_migration_untouched(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = alembic_config()
    fresh_database(config)
    try:
        org, definition = asyncio.run(seed_definition(postgresql_test_url))
        command.downgrade(config, BEFORE)
        asyncio.run(
            insert_old(
                postgresql_test_url,
                org,
                definition,
                [(date(2026, 9, 1), 1, "draft", 1), (date(2026, 8, 1), 2, "approved", 1)],
            )
        )

        error = upgrade_error(config)

        assert isinstance(error, RuntimeError) and "approved" in str(error)
        # Nothing moved: both rows are still there and the database is still at the old revision.
        assert asyncio.run(stored(postgresql_test_url)) == [
            (date(2026, 8, 1), None, None, 2, "approved"),
            (date(2026, 9, 1), None, None, 1, "draft"),
        ]
    finally:
        fresh_database(config)
