"""Location schema, trigger, foreign-key, downgrade, and drift tests."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]


async def scalar(database_url: str, statement: str) -> Any:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.scalar(text(statement))
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_location_migration_and_downgrade(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT version_num FROM alembic_version"))
        == "20260802_0007"
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM information_schema.columns WHERE table_name='locations'",
            )
        )
        == 25
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_trigger WHERE tgname IN "
                "('location_slug_immutable', 'audit_events_append_only') AND NOT tgisinternal",
            )
        )
        == 2
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT convalidated FROM pg_constraint "
                "WHERE conname='fk_audit_events_location_id_locations'",
            )
        )
        is True
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_constraint WHERE conname IN "
                "('fk_locations_organization_id_organizations', "
                "'fk_audit_events_location_id_locations')",
            )
        )
        == 2
    )
    command.check(config)
    command.downgrade(config, "20260802_0001")
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('public.locations')")) is None
    )
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('public.organizations')"))
        == "organizations"
    )
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('public.audit_events')"))
        == "audit_events"
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT to_regprocedure('public.prevent_location_slug_change()')",
            )
        )
        is None
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT to_regprocedure('public.prevent_audit_events_mutation()')",
            )
        )
        is not None
    )
    command.upgrade(config, "head")
