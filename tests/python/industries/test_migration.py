"""Industry migration schema, compatibility, trigger, downgrade, and drift tests."""

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


async def create_legacy_organization(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO organizations "
                    "(id,name,slug,organization_type,status,timezone,default_currency,version) "
                    "VALUES ('50000000-0000-4000-8000-000000000001', "
                    "'Fabricated Legacy Organization','fabricated-legacy-industry',"
                    "'client','prospect','UTC','USD',1)"
                )
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_industry_migration_compatibility_downgrade_and_reupgrade(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "20260802_0002")
    asyncio.run(create_legacy_organization(postgresql_test_url))
    command.upgrade(config, "head")
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT version_num FROM alembic_version"))
        == "20260802_0004"
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM information_schema.columns WHERE table_name='industries'",
            )
        )
        == 12
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT industry_id IS NULL FROM organizations "
                "WHERE id='50000000-0000-4000-8000-000000000001'",
            )
        )
        is True
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname='fk_organizations_industry_id_industries'",
            )
        )
        == "FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE RESTRICT"
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM pg_trigger "
                "WHERE tgname='industry_key_immutable' AND NOT tgisinternal",
            )
        )
        == 1
    )
    command.check(config)
    command.downgrade(config, "20260802_0002")
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('public.industries')")) is None
    )
    assert (
        asyncio.run(
            scalar(
                postgresql_test_url,
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='organizations' AND column_name='industry_id'",
            )
        )
        == 0
    )
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('public.organizations')"))
        == "organizations"
    )
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('public.locations')"))
        == "locations"
    )
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT to_regclass('public.audit_events')"))
        == "audit_events"
    )
    command.upgrade(config, "head")
