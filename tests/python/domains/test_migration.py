"""Organization-domain migration schema, constraint, downgrade, and drift tests."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
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


async def table_names(database_url: str) -> list[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: sorted(inspect(sync_connection).get_table_names())
            )
    finally:
        await engine.dispose()


async def prove_duplicate_and_two_primary_domains_rejected(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO organizations "
                    "(id,name,slug,organization_type,status,timezone,default_currency) VALUES "
                    "('55555555-5555-4555-8555-555555555555','Domain Org',"
                    "'domain-migration-org','test','active','UTC','USD')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO organization_domains "
                    "(id,organization_id,domain,is_primary,status,version) VALUES "
                    "('66666666-6666-4666-8666-666666666666',"
                    "'55555555-5555-4555-8555-555555555555','example.com',true,'active',1)"
                )
            )
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO organization_domains "
                        "(id,organization_id,domain,is_primary,status,version) VALUES "
                        "('77777777-7777-4777-8777-777777777777',"
                        "'55555555-5555-4555-8555-555555555555','example.com',false,'active',1)"
                    )
                )
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO organization_domains "
                        "(id,organization_id,domain,is_primary,status,version) VALUES "
                        "('88888888-8888-4888-8888-888888888888',"
                        "'55555555-5555-4555-8555-555555555555','other.example.com',"
                        "true,'active',1)"
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_organization_domain_migration_constraints_and_downgrade(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    assert "organization_domains" in asyncio.run(table_names(postgresql_test_url))
    asyncio.run(prove_duplicate_and_two_primary_domains_rejected(postgresql_test_url))

    command.downgrade(config, "20260805_0001")
    tables_without_domains = asyncio.run(table_names(postgresql_test_url))
    assert "organization_domains" not in tables_without_domains
    assert "organizations" in tables_without_domains

    command.upgrade(config, "head")
    assert "organization_domains" in asyncio.run(table_names(postgresql_test_url))
    assert (
        asyncio.run(scalar(postgresql_test_url, "SELECT version_num FROM alembic_version"))
        == "20260806_0001"
    )
