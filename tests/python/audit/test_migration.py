"""Audit migration schema and revision-transition tests."""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


async def audit_schema(database_url: str) -> dict[str, object]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: {
                    "tables": sorted(inspect(sync_connection).get_table_names()),
                    "columns": {
                        column["name"]: str(column["type"])
                        for column in inspect(sync_connection).get_columns("audit_events")
                    },
                    "timezone_columns": sorted(
                        column["name"]
                        for column in inspect(sync_connection).get_columns("audit_events")
                        if getattr(column["type"], "timezone", False)
                    ),
                    "checks": sorted(
                        check["name"]
                        for check in inspect(sync_connection).get_check_constraints("audit_events")
                        if check["name"] is not None
                    ),
                    "foreign_keys": sorted(
                        foreign_key["name"]
                        for foreign_key in inspect(sync_connection).get_foreign_keys("audit_events")
                        if foreign_key["name"] is not None
                    ),
                    "indexes": sorted(
                        index["name"]
                        for index in inspect(sync_connection).get_indexes("audit_events")
                        if index["name"] is not None
                    ),
                }
            )
    finally:
        await engine.dispose()


async def trigger_names(database_url: str) -> list[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT trigger_name
                    FROM information_schema.triggers
                    WHERE event_object_schema = 'public'
                      AND event_object_table = 'audit_events'
                    ORDER BY trigger_name
                    """
                )
            )
            return list(result.scalars())
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_audit_migration_upgrades_downgrades_and_restores_head(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(REPOSITORY_ROOT / "alembic.ini")

    command.upgrade(config, "head")
    command.downgrade(config, "20260801_0001")
    command.upgrade(config, "head")
    schema = asyncio.run(audit_schema(postgresql_test_url))
    triggers = asyncio.run(trigger_names(postgresql_test_url))

    assert schema["tables"] == sorted(
        {
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
            "operational_incidents",
            "onboarding_checklist_items",
            "onboarding_step_assignments",
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
        }
    )
    assert schema["columns"] == {
        "action": "VARCHAR(128)",
        "actor_display_reference": "VARCHAR(200)",
        "actor_id": "UUID",
        "actor_type": "VARCHAR(32)",
        "approval_reference_id": "UUID",
        "correlation_id": "VARCHAR(64)",
        "error_code": "VARCHAR(64)",
        "event_type": "VARCHAR(128)",
        "id": "UUID",
        "location_id": "UUID",
        "metadata": "JSONB",
        "occurred_at": "TIMESTAMP",
        "organization_id": "UUID",
        "previous_audit_event_id": "UUID",
        "product_key": "VARCHAR(64)",
        "reason_code": "VARCHAR(64)",
        "recorded_at": "TIMESTAMP",
        "resource_id": "UUID",
        "resource_type": "VARCHAR(100)",
        "result": "VARCHAR(32)",
        "source_ip": "INET",
        "summary": "VARCHAR(500)",
        "user_agent_summary": "VARCHAR(256)",
        "workflow_execution_id": "UUID",
    }
    assert schema["timezone_columns"] == ["occurred_at", "recorded_at"]
    assert schema["checks"] == [
        "ck_audit_events_action_not_blank",
        "ck_audit_events_audit_actor_type",
        "ck_audit_events_audit_result",
        "ck_audit_events_event_type_not_blank",
        "ck_audit_events_metadata_is_object",
        "ck_audit_events_summary_not_blank",
    ]
    assert schema["foreign_keys"] == [
        "fk_audit_events_location_id_locations",
        "fk_audit_events_organization_id_organizations",
        "fk_audit_events_previous_audit_event_id_audit_events",
    ]
    assert schema["indexes"] == [
        "ix_audit_events_correlation_id",
        "ix_audit_events_location_occurred_at_id",
        "ix_audit_events_occurred_at_id",
        "ix_audit_events_organization_occurred_at_id",
        "ix_audit_events_previous_audit_event_id",
        "ix_audit_events_resource_occurred_at_id",
    ]
    assert triggers == ["audit_events_append_only"] * 2

    command.downgrade(config, "20260801_0001")
    engine = create_async_engine(postgresql_test_url)
    try:

        async def tables_at_prior_revision() -> list[str]:
            async with engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync_connection: sorted(inspect(sync_connection).get_table_names())
                )

        assert asyncio.run(tables_at_prior_revision()) == ["alembic_version"]
    finally:
        asyncio.run(engine.dispose())

    command.upgrade(config, "head")
