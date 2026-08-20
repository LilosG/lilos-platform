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
    alembic_head: str,
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = alembic_config()

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    tables_at_head, revisions_at_head = asyncio.run(database_state(postgresql_test_url))
    assert tables_at_head == [
        "ai_executions",
        "ai_task_definitions",
        "alembic_version",
        "analytics_properties",
        "audit_events",
        "business_fact_revisions",
        "business_knowledge_documents",
        "configuration_definitions",
        "configuration_revisions",
        "content_briefs",
        "content_items",
        "content_opportunities",
        "content_publications",
        "content_revisions",
        "crm_lead_mappings",
        "execution_idempotency_records",
        "feature_flag_revisions",
        "gbp_accounts",
        "gbp_capability_snapshots",
        "gbp_categories",
        "gbp_change_sets",
        "gbp_locations",
        "gbp_media",
        "gbp_post_publications",
        "gbp_post_revisions",
        "gbp_profile_change_revisions",
        "gbp_profile_snapshots",
        "gbp_provider_posts",
        "gbp_publications",
        "gbp_special_hours",
        "gbp_suspension_cases",
        "incident_timeline_entries",
        "industries",
        "insight_annotations",
        "insight_goals",
        "insight_records",
        "insight_sources",
        "integration_connections",
        "integration_providers",
        "job_attempts",
        "jobs",
        "lead_communications",
        "lead_consents",
        "lead_notes",
        "lead_sources",
        "lead_status_history",
        "lead_submissions",
        "lead_suppressions",
        "lead_tasks",
        "leads",
        "location_group_memberships",
        "location_groups",
        "location_profiles",
        "locations",
        "membership_permission_denies",
        "membership_role_assignments",
        "metric_definitions",
        "metric_observations",
        "notification_deliveries",
        "notification_delivery_attempts",
        "notification_events",
        "notification_preferences",
        "notification_templates",
        "oauth_authorization_intents",
        "offboarding_plans",
        "offboarding_steps",
        "onboarding_checklist_items",
        "onboarding_step_assignments",
        "operational_incidents",
        "organization_domains",
        "organization_invitations",
        "organization_memberships",
        "organization_profiles",
        "organizations",
        "permissions",
        "platform_administrators",
        "policy_revisions",
        "product_entitlement_locations",
        "product_entitlements",
        "products",
        "provider_resource_mappings",
        "provider_secrets",
        "provider_state_snapshots",
        "publishing_targets",
        "report_definitions",
        "report_deliveries",
        "report_revisions",
        "review_escalations",
        "review_response_revisions",
        "review_revisions",
        "review_risk_flags",
        "reviews",
        "role_permissions",
        "roles",
        "runtime_control_revisions",
        "seo_crawl_runs",
        "seo_implementation_tasks",
        "seo_opportunities",
        "seo_outcomes",
        "seo_pages",
        "seo_recommendation_revisions",
        "seo_search_observations",
        "seo_search_properties",
        "seo_websites",
        "service_assignments",
        "service_catalog",
        "service_heartbeats",
        "slo_definitions",
        "sync_change_intents",
        "sync_checkpoints",
        "sync_conflicts",
        "sync_definitions",
        "sync_runs",
        "user_profiles",
        "workflow_definitions",
        "workflow_runs",
        "workflow_schedules",
        "workflow_steps",
        "workflow_versions",
    ]
    assert revisions_at_head == [alembic_head]

    command.downgrade(config, "base")
    tables_at_base, revisions_at_base = asyncio.run(database_state(postgresql_test_url))
    assert tables_at_base == ["alembic_version"]
    assert revisions_at_base == []

    command.upgrade(config, "head")
    tables_at_final_head, revisions_at_final_head = asyncio.run(database_state(postgresql_test_url))
    assert tables_at_final_head == [
        "ai_executions",
        "ai_task_definitions",
        "alembic_version",
        "analytics_properties",
        "audit_events",
        "business_fact_revisions",
        "business_knowledge_documents",
        "configuration_definitions",
        "configuration_revisions",
        "content_briefs",
        "content_items",
        "content_opportunities",
        "content_publications",
        "content_revisions",
        "crm_lead_mappings",
        "execution_idempotency_records",
        "feature_flag_revisions",
        "gbp_accounts",
        "gbp_capability_snapshots",
        "gbp_categories",
        "gbp_change_sets",
        "gbp_locations",
        "gbp_media",
        "gbp_post_publications",
        "gbp_post_revisions",
        "gbp_profile_change_revisions",
        "gbp_profile_snapshots",
        "gbp_provider_posts",
        "gbp_publications",
        "gbp_special_hours",
        "gbp_suspension_cases",
        "incident_timeline_entries",
        "industries",
        "insight_annotations",
        "insight_goals",
        "insight_records",
        "insight_sources",
        "integration_connections",
        "integration_providers",
        "job_attempts",
        "jobs",
        "lead_communications",
        "lead_consents",
        "lead_notes",
        "lead_sources",
        "lead_status_history",
        "lead_submissions",
        "lead_suppressions",
        "lead_tasks",
        "leads",
        "location_group_memberships",
        "location_groups",
        "location_profiles",
        "locations",
        "membership_permission_denies",
        "membership_role_assignments",
        "metric_definitions",
        "metric_observations",
        "notification_deliveries",
        "notification_delivery_attempts",
        "notification_events",
        "notification_preferences",
        "notification_templates",
        "oauth_authorization_intents",
        "offboarding_plans",
        "offboarding_steps",
        "onboarding_checklist_items",
        "onboarding_step_assignments",
        "operational_incidents",
        "organization_domains",
        "organization_invitations",
        "organization_memberships",
        "organization_profiles",
        "organizations",
        "permissions",
        "platform_administrators",
        "policy_revisions",
        "product_entitlement_locations",
        "product_entitlements",
        "products",
        "provider_resource_mappings",
        "provider_secrets",
        "provider_state_snapshots",
        "publishing_targets",
        "report_definitions",
        "report_deliveries",
        "report_revisions",
        "review_escalations",
        "review_response_revisions",
        "review_revisions",
        "review_risk_flags",
        "reviews",
        "role_permissions",
        "roles",
        "runtime_control_revisions",
        "seo_crawl_runs",
        "seo_implementation_tasks",
        "seo_opportunities",
        "seo_outcomes",
        "seo_pages",
        "seo_recommendation_revisions",
        "seo_search_observations",
        "seo_search_properties",
        "seo_websites",
        "service_assignments",
        "service_catalog",
        "service_heartbeats",
        "slo_definitions",
        "sync_change_intents",
        "sync_checkpoints",
        "sync_conflicts",
        "sync_definitions",
        "sync_runs",
        "user_profiles",
        "workflow_definitions",
        "workflow_runs",
        "workflow_schedules",
        "workflow_steps",
        "workflow_versions",
    ]
    assert revisions_at_final_head == [alembic_head]


@pytest.mark.integration
def test_20260812_0001_catalog_correction_survives_immutability_trigger(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catalog correction can UPDATE products despite products_governed_immutability.

    Migration 20260803_0001 installs a BEFORE UPDATE trigger that raises
    "catalog or operational revision is immutable" for the products table.
    Migration 20260812_0001 must temporarily disable *only* that trigger,
    run the correction, and re-enable it — leaving immutability enforcement
    fully operational after the transaction commits.

    Alembic commands run synchronously (they internally use asyncio.run).
    Async DB queries run in their own short-lived asyncio.run() calls so
    they never overlap with an active Alembic event loop.
    """
    import uuid

    from alembic.command import downgrade as alembic_downgrade
    from alembic.command import upgrade as alembic_upgrade
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = alembic_config()
    engine = create_async_engine(postgresql_test_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # ---------- sync: initialise schema at head ----------
    alembic_downgrade(config, "base")
    alembic_upgrade(config, "head")

    # ---------- async: seed product rows ----------
    gbp_id = uuid.uuid4()
    reviews_id = uuid.uuid4()

    async def _seed() -> None:
        async with session_factory.begin() as s:
            for row in (
                (gbp_id, "gbp", "Google Business Profile", True),
                (reviews_id, "reviews", "Reviews", True),
            ):
                await s.execute(
                    sa_text(
                        "INSERT INTO products (id, key, name, description, owning_module, "
                        "current_product_version, runtime_control_namespace, "
                        "requires_location_profile) "
                        "VALUES (:id, :key, :name, :desc, 'platform', '1.0', :key, :rlp)"
                    ),
                    {
                        "id": row[0],
                        "key": row[1],
                        "name": row[2],
                        "desc": row[2],
                        "rlp": row[3],
                    },
                )

    asyncio.run(_seed())

    async def _select_requires_location_profile(key: str) -> bool:
        async with session_factory() as s:
            result = await s.execute(
                sa_text("SELECT requires_location_profile FROM products WHERE key = :key"),
                {"key": key},
            )
            return result.scalar()  # type: ignore[return-value]

    # Verify seeded state.
    for key in ("gbp", "reviews"):
        assert asyncio.run(_select_requires_location_profile(key)) is True, (
            f"{key} should start true"
        )

    try:
        # ---------- sync: downgrade to just before 20260812_0001 ----------
        alembic_downgrade(config, "20260811_0002")

        # Verify downgrade restored true.
        for key in ("gbp", "reviews"):
            assert asyncio.run(_select_requires_location_profile(key)) is True, (
                f"{key} should be true after downgrade"
            )

        # Verify trigger is active.
        async def _trigger_active() -> bool:
            try:
                async with session_factory.begin() as s:
                    await s.execute(sa_text("UPDATE products SET name = 'hack' WHERE key = 'gbp'"))
                return False
            except Exception as exc:
                assert "immutable" in str(exc).lower()
                return True

        assert asyncio.run(_trigger_active()), (
            "products_governed_immutability trigger must be active after downgrade"
        )

        # ---------- sync: upgrade through 20260812_0001 ----------
        alembic_upgrade(config, "20260812_0001")

        # Verify upgrade restored false.
        for key in ("gbp", "reviews"):
            assert asyncio.run(_select_requires_location_profile(key)) is False, (
                f"{key} should be false after upgrade"
            )

        # Verify trigger is STILL active.
        assert asyncio.run(_trigger_active()), (
            "products_governed_immutability trigger must be active after upgrade"
        )

    finally:
        # ---------- sync: always restore head ----------
        alembic_upgrade(config, "head")
