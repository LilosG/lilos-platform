"""Location-group migration schema, integrity, downgrade, and drift tests."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]


async def scalar(database_url: str, statement: str) -> Any:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.scalar(text(statement))
    finally:
        await engine.dispose()


async def prove_cross_organization_membership_rejected(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO organizations "
                    "(id,name,slug,organization_type,status,timezone,default_currency) VALUES "
                    "('11111111-1111-4111-8111-111111111111','One','group-migration-one',"
                    "'test','active','UTC','USD'),"
                    "('22222222-2222-4222-8222-222222222222','Two','group-migration-two',"
                    "'test','active','UTC','USD')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO locations "
                    "(id,organization_id,name,slug,location_type,status,timezone,country_code,"
                    "website_url) VALUES "
                    "('33333333-3333-4333-8333-333333333333',"
                    "'11111111-1111-4111-8111-111111111111','Virtual','group-virtual',"
                    "'virtual','active','UTC','US','https://example.invalid')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO location_groups (id,organization_id,name,key) VALUES "
                    "('44444444-4444-4444-8444-444444444444',"
                    "'22222222-2222-4222-8222-222222222222','Group','migration-group')"
                )
            )
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO location_group_memberships "
                        "(id,organization_id,location_group_id,location_id) VALUES "
                        "('55555555-5555-4555-8555-555555555555',"
                        "'11111111-1111-4111-8111-111111111111',"
                        "'44444444-4444-4444-8444-444444444444',"
                        "'33333333-3333-4333-8333-333333333333')"
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_location_group_migration_integrity_downgrade_and_reupgrade(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT version_num FROM alembic_version"))
        == "20260804_0001"
    )
    assert asyncio.run(
        scalar(
            postgresql_test_url,
            "SELECT array_agg(column_name ORDER BY ordinal_position)::text "
            "FROM information_schema.columns WHERE table_name='location_groups'",
        )
    ) == (
        "{organization_id,name,key,description,status,archived_at,version,id,created_at,updated_at}"
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT array_agg(column_name ORDER BY ordinal_position)::text "
                "FROM information_schema.columns WHERE table_name='location_group_memberships'",
            )
        )
        == "{organization_id,location_group_id,location_id,id,created_at}"
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_constraint WHERE conname IN "
                "('fk_location_groups_organization_id_organizations',"
                "'fk_lg_memberships_organization_id_organizations',"
                "'fk_lg_memberships_organization_group',"
                "'fk_lg_memberships_organization_location') "
                "AND confdeltype='r' AND convalidated",
            )
        )
        == 4
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_constraint WHERE conname IN "
                "('uq_location_groups_organization_id_key',"
                "'uq_lg_memberships_organization_group_location')",
            )
        )
        == 2
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_trigger WHERE "
                "tgname='location_groups_immutable_key' AND NOT tgisinternal",
            )
        )
        == 1
    )
    asyncio.run(prove_cross_organization_membership_rejected(postgresql_test_url))
    command.check(config)
    command.downgrade(config, "20260802_0004")
    assert asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('location_groups')")) is None
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('location_group_memberships')"))
        is None
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT to_regprocedure('prevent_location_group_key_change()')",
            )
        )
        is None
    )
    for table_name in (
        "organizations",
        "industries",
        "locations",
        "organization_profiles",
        "location_profiles",
        "audit_events",
    ):
        assert (
            asyncio.run(scalar(postgresql_test_url, f"SELECT to_regclass('public.{table_name}')"))
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
    command.upgrade(config, "head")
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT version_num FROM alembic_version"))
        == "20260804_0001"
    )
