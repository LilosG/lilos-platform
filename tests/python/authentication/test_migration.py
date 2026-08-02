"""User-profile migration schema, trigger, downgrade, and drift tests."""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.integration
def test_user_profile_migration_and_phase_two_preservation(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)

    async def inspect_head() -> None:
        engine = create_async_engine(postgresql_test_url)
        try:
            async with engine.connect() as connection:
                columns = await connection.run_sync(
                    lambda sync: inspect(sync).get_columns("user_profiles")
                )
                unique = await connection.run_sync(
                    lambda sync: inspect(sync).get_unique_constraints("user_profiles")
                )
                triggers = await connection.execute(
                    text(
                        "SELECT tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                        "WHERE c.relname='user_profiles' AND NOT t.tgisinternal"
                    )
                )
                assert [column["name"] for column in columns] == [
                    "id",
                    "auth_user_id",
                    "email",
                    "display_name",
                    "status",
                    "deactivated_at",
                    "created_at",
                    "updated_at",
                    "version",
                ]
                assert {item["name"] for item in unique} == {"uq_user_profiles_auth_user_id"}
                assert list(triggers.scalars()) == ["user_profiles_immutable_auth_subject"]
        finally:
            await engine.dispose()

    asyncio.run(inspect_head())
    command.downgrade(config, "20260802_0005")

    async def inspect_downgrade() -> None:
        engine = create_async_engine(postgresql_test_url)
        try:
            async with engine.connect() as connection:
                tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
                assert "user_profiles" not in tables
                assert {
                    "organizations",
                    "industries",
                    "locations",
                    "organization_profiles",
                    "location_profiles",
                    "location_groups",
                    "location_group_memberships",
                    "audit_events",
                }.issubset(tables)
                trigger = await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                        "WHERE c.relname='audit_events' AND tgname='audit_events_append_only'"
                    )
                )
                assert trigger == 1
        finally:
            await engine.dispose()

    asyncio.run(inspect_downgrade())
    command.upgrade(config, "head")
