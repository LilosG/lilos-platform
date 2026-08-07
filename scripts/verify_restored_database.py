"""Verify a synthetic PostgreSQL restore without exposing row content."""

import asyncio
import os
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

REQUIRED_TABLES = {
    "audit_events",
    "organizations",
    "organization_memberships",
    "jobs",
    "integration_connections",
    "seo_websites",
    "metric_definitions",
    "operational_incidents",
}

ROOT = Path(__file__).resolve().parent.parent


def _current_alembic_head() -> str:
    config = Config(ROOT / "alembic.ini")
    script_dir = ScriptDirectory.from_config(config)
    head = script_dir.get_current_head()
    assert head is not None, "no Alembic head revision found"
    return head


async def verify(database_url: str) -> None:
    expected_head = _current_alembic_head()
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != expected_head:
                raise RuntimeError(
                    f"restored database migration head mismatch: "
                    f"expected {expected_head}, got {revision}"
                )
            table_rows = await connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
            missing = REQUIRED_TABLES - set(table_rows.scalars())
            if missing:
                raise RuntimeError("restored database is missing required structures")
            trigger = await connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.triggers "
                    "WHERE trigger_name='audit_events_append_only'"
                )
            )
            if trigger != 2:
                raise RuntimeError("restored database audit append-only trigger mismatch")
    finally:
        await engine.dispose()


def main() -> int:
    database_url = os.getenv("LILOS_RESTORE_DATABASE_URL")
    if not database_url or "test" not in database_url.casefold():
        raise RuntimeError("LILOS_RESTORE_DATABASE_URL must identify a synthetic test database")
    asyncio.run(verify(database_url))
    print(f"synthetic restore verified at {_current_alembic_head()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
