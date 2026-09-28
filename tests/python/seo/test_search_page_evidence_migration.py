"""The page-evidence migration must use its exact named check constraints."""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]
TABLES = ("seo_search_observations", "metric_observations")
MARKER = "lilos:20260925_0001"


async def check_constraints(database_url: str) -> list[tuple[str, str, str | None]]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT t.relname, c.conname, obj_description(c.oid, 'pg_constraint') "
                    "FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                    "JOIN pg_namespace n ON n.oid = t.relnamespace "
                    "WHERE n.nspname = current_schema() AND t.relname IN :tables "
                    "AND c.conname LIKE '%page_requires_website%' AND c.contype = 'c'"
                ).bindparams(bindparam("tables", expanding=True)),
                {"tables": TABLES},
            )
            return sorted((table, name, comment) for table, name, comment in rows)
    finally:
        await engine.dispose()


async def remove_preexisting_checks(database_url: str) -> None:
    """Reproduce the production schema where these checks are absent."""
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for table in TABLES:
                statement = (
                    f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "
                    f"ck_{table}_page_requires_website"
                )
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_page_evidence_check_names_and_markers_survive_upgrade_downgrade(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "20260924_0001")
    asyncio.run(remove_preexisting_checks(postgresql_test_url))
    command.upgrade(config, "20260925_0001")

    expected = sorted((table, f"ck_{table}_page_requires_website", MARKER) for table in TABLES)
    assert asyncio.run(check_constraints(postgresql_test_url)) == expected

    command.downgrade(config, "20260924_0001")
    assert asyncio.run(check_constraints(postgresql_test_url)) == []
    command.upgrade(config, "20260925_0001")
    assert asyncio.run(check_constraints(postgresql_test_url)) == expected
    command.upgrade(config, "head")
