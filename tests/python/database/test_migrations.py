import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def alembic_config() -> Config:
    return Config(REPOSITORY_ROOT / "alembic.ini")


async def database_state(database_url: str) -> tuple[list[str], list[str]]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
            revisions: list[str] = []
            if "alembic_version" in tables:
                result = await connection.execute(text("SELECT version_num FROM alembic_version"))
                revisions = list(result.scalars())
            return sorted(tables), revisions
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_baseline_migration_upgrades_downgrades_and_upgrades_again(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = alembic_config()

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    tables_at_head, revisions_at_head = asyncio.run(database_state(postgresql_test_url))
    assert tables_at_head == [
        "alembic_version",
        "audit_events",
        "business_fact_revisions",
        "configuration_definitions",
        "configuration_revisions",
        "feature_flag_revisions",
        "industries",
        "location_group_memberships",
        "location_groups",
        "location_profiles",
        "locations",
        "membership_permission_denies",
        "membership_role_assignments",
        "offboarding_plans",
        "offboarding_steps",
        "onboarding_checklist_items",
        "organization_invitations",
        "organization_memberships",
        "organization_profiles",
        "organizations",
        "permissions",
        "policy_revisions",
        "product_entitlement_locations",
        "product_entitlements",
        "products",
        "role_permissions",
        "roles",
        "runtime_control_revisions",
        "service_assignments",
        "service_catalog",
        "user_profiles",
    ]
    assert revisions_at_head == ["20260803_0001"]

    command.downgrade(config, "base")
    tables_at_base, revisions_at_base = asyncio.run(database_state(postgresql_test_url))
    assert tables_at_base == ["alembic_version"]
    assert revisions_at_base == []

    command.upgrade(config, "head")
    tables_at_final_head, revisions_at_final_head = asyncio.run(database_state(postgresql_test_url))
    assert tables_at_final_head == [
        "alembic_version",
        "audit_events",
        "business_fact_revisions",
        "configuration_definitions",
        "configuration_revisions",
        "feature_flag_revisions",
        "industries",
        "location_group_memberships",
        "location_groups",
        "location_profiles",
        "locations",
        "membership_permission_denies",
        "membership_role_assignments",
        "offboarding_plans",
        "offboarding_steps",
        "onboarding_checklist_items",
        "organization_invitations",
        "organization_memberships",
        "organization_profiles",
        "organizations",
        "permissions",
        "policy_revisions",
        "product_entitlement_locations",
        "product_entitlements",
        "products",
        "role_permissions",
        "roles",
        "runtime_control_revisions",
        "service_assignments",
        "service_catalog",
        "user_profiles",
    ]
    assert revisions_at_final_head == ["20260803_0001"]
