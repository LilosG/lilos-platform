"""Access-domain migration, schema, downgrade, and preservation validation."""

import asyncio
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]


async def catalog(database_url: str) -> dict[str, object]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            tables = set(
                (
                    await connection.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                    )
                ).scalars()
            )
            triggers = set(
                (
                    await connection.execute(
                        text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
                    )
                ).scalars()
            )
            constraints = set(
                (await connection.execute(text("SELECT conname FROM pg_constraint"))).scalars()
            )
            indexes = set(
                (
                    await connection.execute(
                        text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
                    )
                ).scalars()
            )
        return {
            "revision": revision,
            "tables": tables,
            "triggers": triggers,
            "constraints": constraints,
            "indexes": indexes,
        }
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_access_migration_upgrade_downgrade_and_preservation(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.upgrade(config, "head")
    state = asyncio.run(catalog(postgresql_test_url))
    expected = {
        "organization_memberships",
        "organization_invitations",
        "roles",
        "permissions",
        "role_permissions",
        "membership_role_assignments",
        "membership_permission_denies",
    }
    assert state["revision"] == "20260805_0002"
    assert expected <= cast(set[str], state["tables"])
    assert {
        "organization_memberships_immutable_type",
        "roles_immutable_key",
        "permissions_immutable_key",
        "audit_events_append_only",
    } <= cast(set[str], state["triggers"])
    assert {
        "uq_memberships_organization_user",
        "fk_membership_role_assignments_organization_membership",
        "fk_membership_permission_denies_organization_location",
    } <= cast(set[str], state["constraints"])
    assert {
        "uq_role_assignments_organization_scope",
        "uq_permission_denies_location_scope",
        "uq_invitations_pending_organization_email",
    } <= cast(set[str], state["indexes"])
    command.check(config)
    command.downgrade(config, "20260802_0006")
    downgraded = asyncio.run(catalog(postgresql_test_url))
    assert not expected & cast(set[str], downgraded["tables"])
    assert {
        "user_profiles",
        "organizations",
        "locations",
        "location_groups",
        "organization_profiles",
        "audit_events",
    } <= cast(set[str], downgraded["tables"])
    assert "audit_events_append_only" in cast(set[str], downgraded["triggers"])
    command.upgrade(config, "head")
    assert asyncio.run(catalog(postgresql_test_url))["revision"] == "20260805_0002"
