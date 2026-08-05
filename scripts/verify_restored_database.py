"""Verify a synthetic PostgreSQL restore without exposing row content."""

import asyncio
import os

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


async def verify(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "20260804_0002":
                raise RuntimeError("restored database migration head mismatch")
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
    print("synthetic restore verified at 20260804_0002")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
