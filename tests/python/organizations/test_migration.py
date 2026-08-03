"""Organization migration, schema, foreign-key, and drift validation."""

import asyncio
from pathlib import Path
from typing import TypedDict, cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class CatalogState(TypedDict):
    revision: str | None
    columns: list[tuple[str, str, str]]
    constraints: list[tuple[str, str]]
    audit_foreign_keys: list[tuple[str, str]]
    indexes: list[str]
    triggers: list[str]


async def catalog(database_url: str) -> CatalogState:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            columns = cast(
                list[tuple[str, str, str]],
                list(
                    (
                        await connection.execute(
                            text(
                                "SELECT column_name, data_type, is_nullable "
                                "FROM information_schema.columns "
                                "WHERE table_schema = 'public' AND table_name = 'organizations' "
                                "ORDER BY ordinal_position"
                            )
                        )
                    ).tuples()
                ),
            )
            constraints = cast(
                list[tuple[str, str]],
                list(
                    (
                        await connection.execute(
                            text(
                                "SELECT conname, contype FROM pg_constraint "
                                "WHERE conrelid = 'public.organizations'::regclass ORDER BY conname"
                            )
                        )
                    ).tuples()
                ),
            )
            audit_foreign_keys = cast(
                list[tuple[str, str]],
                list(
                    (
                        await connection.execute(
                            text(
                                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                                "WHERE conrelid = 'public.audit_events'::regclass "
                                "AND contype = 'f' "
                                "AND conname = 'fk_audit_events_organization_id_organizations' "
                                "ORDER BY conname"
                            )
                        )
                    ).tuples()
                ),
            )
            indexes = cast(
                list[str],
                list(
                    (
                        await connection.execute(
                            text(
                                "SELECT indexname FROM pg_indexes "
                                "WHERE schemaname = 'public' AND tablename = 'organizations' "
                                "ORDER BY indexname"
                            )
                        )
                    ).scalars()
                ),
            )
            triggers = cast(
                list[str],
                list(
                    (
                        await connection.execute(
                            text(
                                "SELECT tgname FROM pg_trigger "
                                "WHERE tgrelid = 'public.organizations'::regclass "
                                "AND NOT tgisinternal ORDER BY tgname"
                            )
                        )
                    ).scalars()
                ),
            )
            return {
                "revision": revision,
                "columns": columns,
                "constraints": constraints,
                "audit_foreign_keys": audit_foreign_keys,
                "indexes": indexes,
                "triggers": triggers,
            }
    finally:
        await engine.dispose()


async def downgraded_state(database_url: str) -> tuple[object, object, object, object]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return (
                await connection.scalar(text("SELECT version_num FROM alembic_version")),
                await connection.scalar(text("SELECT to_regclass('public.organizations')")),
                await connection.scalar(text("SELECT to_regclass('public.audit_events')")),
                await connection.scalar(
                    text("SELECT to_regprocedure('public.prevent_organization_slug_change()')")
                ),
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_organization_migration_schema_drift_downgrade_and_reupgrade(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    state = asyncio.run(catalog(postgresql_test_url))
    assert state["revision"] == "20260803_0012"
    assert len(state["columns"]) == 20
    assert ("created_at", "timestamp with time zone", "NO") in state["columns"]
    assert ("updated_at", "timestamp with time zone", "NO") in state["columns"]
    assert ("archived_at", "timestamp with time zone", "YES") in state["columns"]
    constraint_names = {name for name, _ in state["constraints"]}
    assert {
        "ck_organizations_organization_status",
        "ck_organizations_organization_type",
        "ck_organizations_slug_format",
        "ck_organizations_slug_not_reserved",
        "ck_organizations_version_positive",
        "pk_organizations",
        "uq_organizations_slug",
    } <= constraint_names
    assert state["audit_foreign_keys"] == [
        (
            "fk_audit_events_organization_id_organizations",
            "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE RESTRICT",
        )
    ]
    assert state["indexes"] == [
        "ix_organizations_created_at_id",
        "pk_organizations",
        "uq_organizations_slug",
    ]
    assert state["triggers"] == ["organization_slug_immutable"]
    command.check(config)

    command.downgrade(config, "20260801_0002")
    revision, organizations_table, audit_table, slug_function = asyncio.run(
        downgraded_state(postgresql_test_url)
    )
    assert revision == "20260801_0002"
    assert organizations_table is None
    assert audit_table == "audit_events"
    assert slug_function is None

    command.upgrade(config, "head")
    assert asyncio.run(catalog(postgresql_test_url))["revision"] == "20260803_0012"
