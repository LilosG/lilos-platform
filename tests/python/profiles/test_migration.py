"""Profile migration schema, ownership, downgrade preservation, and drift tests."""

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
def test_profile_migration_schema_downgrade_preservation_and_reupgrade(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT version_num FROM alembic_version"))
        == "20260802_0005"
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='organization_profiles'",
            )
        )
        == 16
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='location_profiles'",
            )
        )
        == 15
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_constraint WHERE conname IN "
                "('fk_organization_profiles_organization_id_organizations',"
                "'fk_location_profiles_organization_id_organizations',"
                "'fk_location_profiles_organization_location_locations') "
                "AND confdeltype='r'",
            )
        )
        == 3
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_constraint "
                "WHERE conname='uq_locations_organization_id_id'",
            )
        )
        == 1
    )
    command.check(config)
    command.downgrade(config, "20260802_0003")
    assert (
        asyncio.run(
            scalar(postgresql_test_url, "SELECT to_regclass('public.organization_profiles')")
        )
        is None
    )
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('public.location_profiles')"))
        is None
    )
    for table_name in ("organizations", "industries", "locations", "audit_events"):
        assert (
            asyncio.run(
                scalar(
                    postgresql_test_url,
                    f"SELECT to_regclass('public.{table_name}')",
                )
            )
            == table_name
        )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_trigger WHERE "
                "tgname='audit_events_append_only' AND NOT tgisinternal",
            )
        )
        == 1
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_constraint "
                "WHERE conname='uq_locations_organization_id_id'",
            )
        )
        == 0
    )
    command.upgrade(config, "head")
