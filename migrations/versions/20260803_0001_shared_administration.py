# ruff: noqa: E501
"""Create shared administration and configuration foundations.

Revision ID: 20260803_0001
Revises: 20260802_0007
Create Date: 2026-08-03

Governed revision rows retain history; audit records retain ordinary UUID references and therefore
remain valid after downgrade without foreign keys to Phase 4 resources.
"""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.administration.models import (
    BusinessFactRevision,
    ConfigurationDefinition,
    ConfigurationRevision,
    FeatureFlagRevision,
    OffboardingPlan,
    OffboardingStep,
    OnboardingChecklistItem,
    PolicyRevision,
    Product,
    ProductEntitlement,
    ProductEntitlementLocation,
    RuntimeControlRevision,
    ServiceAssignment,
    ServiceDefinition,
)

revision: str = "20260803_0001"
down_revision: str | Sequence[str] | None = "20260802_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES: tuple[Table, ...] = tuple(
    cast(Table, model.__table__)
    for model in (
        ServiceDefinition,
        ServiceAssignment,
        BusinessFactRevision,
        Product,
        ProductEntitlement,
        ProductEntitlementLocation,
        ConfigurationDefinition,
        ConfigurationRevision,
        PolicyRevision,
        FeatureFlagRevision,
        RuntimeControlRevision,
        OnboardingChecklistItem,
        OffboardingPlan,
        OffboardingStep,
    )
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=False)
    op.execute("""
        CREATE FUNCTION prevent_phase4_identity_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_TABLE_NAME IN ('service_catalog','products','configuration_definitions')
             AND (to_jsonb(NEW)->>'key') IS DISTINCT FROM (to_jsonb(OLD)->>'key') THEN
            RAISE EXCEPTION 'stable key is immutable' USING ERRCODE='23514';
          END IF;
          IF TG_TABLE_NAME = 'business_fact_revisions'
             AND OLD.status IN ('approved','active','superseded','expired')
             AND ((to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status')
                  OR NEW.status NOT IN ('superseded','expired')) THEN
            RAISE EXCEPTION 'governed fact content is immutable' USING ERRCODE='23514';
          END IF;
          IF TG_TABLE_NAME IN ('configuration_revisions','policy_revisions')
             AND OLD.status IN ('approved','scheduled','active','superseded','expired')
             AND ((to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status')
                  OR NEW.status NOT IN ('superseded','expired','revoked','archived')) THEN
            RAISE EXCEPTION 'approved revision content is immutable' USING ERRCODE='23514';
          END IF;
          IF TG_TABLE_NAME IN ('products','configuration_definitions','feature_flag_revisions','runtime_control_revisions') THEN
            RAISE EXCEPTION 'catalog or operational revision is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$
    """)
    for table_name in (
        "service_catalog",
        "products",
        "configuration_definitions",
        "business_fact_revisions",
        "configuration_revisions",
        "policy_revisions",
        "feature_flag_revisions",
        "runtime_control_revisions",
    ):
        op.execute(
            f"CREATE TRIGGER {table_name}_governed_immutability BEFORE UPDATE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_phase4_identity_change()"
        )
    op.execute("""
        CREATE FUNCTION prevent_phase4_governed_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'governed Phase 4 history cannot be deleted' USING ERRCODE='23514';
        END; $$
    """)
    for table_name in (
        "service_catalog",
        "service_assignments",
        "business_fact_revisions",
        "products",
        "product_entitlements",
        "product_entitlement_locations",
        "configuration_definitions",
        "configuration_revisions",
        "policy_revisions",
        "feature_flag_revisions",
        "runtime_control_revisions",
        "onboarding_checklist_items",
        "offboarding_plans",
        "offboarding_steps",
    ):
        op.execute(
            f"CREATE TRIGGER {table_name}_governed_no_delete BEFORE DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_phase4_governed_delete()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=False)
    op.execute("DROP FUNCTION IF EXISTS prevent_phase4_governed_delete()")
    op.execute("DROP FUNCTION IF EXISTS prevent_phase4_identity_change()")
