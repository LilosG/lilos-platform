"""Add cross-product Growth opportunity planning persistence.

The Growth product coordinates authoritative SEO, Analytics, GBP, Reviews,
Content, and workflow evidence. These tables store planning state and source
references only; they do not duplicate canonical product observations.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260908_0001"
down_revision: str | Sequence[str] | None = "20260827_0001"
branch_labels = depends_on = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "growth_opportunities",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("opportunity_type", sa.String(length=64), nullable=False),
        sa.Column("primary_topic", sa.String(length=500), nullable=True),
        sa.Column("target_reference", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("impact_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("priority_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.Column("source_references", _jsonb(), nullable=False),
        sa.Column("evidence_summary", _jsonb(), nullable=False),
        sa.Column("baseline_metrics", _jsonb(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('detected','planning','planned','executing','measuring','succeeded',"
            "'no_material_change','negative','dismissed','archived')",
            name=op.f("ck_growth_opportunities_status"),
        ),
        sa.CheckConstraint(
            "impact_score >= 0 AND impact_score <= 100",
            name=op.f("ck_growth_opportunities_impact_score_range"),
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name=op.f("ck_growth_opportunities_confidence_score_range"),
        ),
        sa.CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100",
            name=op.f("ck_growth_opportunities_priority_score_range"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_growth_opportunities")),
        sa.UniqueConstraint("organization_id", "id", name="uq_growth_opportunities_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "deduplication_key",
            name="uq_growth_opportunities_org_deduplication_key",
        ),
    )
    op.create_index(
        "ix_growth_opportunities_org_status_priority",
        "growth_opportunities",
        ["organization_id", "status", "priority_score"],
    )

    op.create_table(
        "growth_action_plans",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("strategy", sa.Text(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_references", _jsonb(), nullable=False),
        sa.Column("planner_metadata", _jsonb(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft','ready','executing','blocked','completed','cancelled')",
            name=op.f("ck_growth_action_plans_status"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "opportunity_id"],
            ["growth_opportunities.organization_id", "growth_opportunities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_growth_action_plans")),
        sa.UniqueConstraint("organization_id", "id", name="uq_growth_action_plans_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "opportunity_id",
            "plan_version",
            name="uq_growth_action_plans_opportunity_version",
        ),
    )

    op.create_table(
        "growth_action_items",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_reference", sa.Text(), nullable=True),
        sa.Column("parameters", _jsonb(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("approval_mode", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verification_status", sa.String(length=24), nullable=False),
        sa.Column("verification_evidence", _jsonb(), nullable=False),
        sa.Column("safe_error_code", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "risk_level IN ('low','medium','high','restricted')",
            name=op.f("ck_growth_action_items_risk_level"),
        ),
        sa.CheckConstraint(
            "approval_mode IN ('inherit','automatic','human_required')",
            name=op.f("ck_growth_action_items_approval_mode"),
        ),
        sa.CheckConstraint(
            "status IN ('planned','waiting_approval','authorized','queued','executing','verifying',"
            "'completed','failed','cancelled','skipped')",
            name=op.f("ck_growth_action_items_status"),
        ),
        sa.CheckConstraint(
            "verification_status IN ('pending','not_required','verified','failed')",
            name=op.f("ck_growth_action_items_verification_status"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "plan_id"],
            ["growth_action_plans.organization_id", "growth_action_plans.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_growth_action_items")),
        sa.UniqueConstraint("organization_id", "id", name="uq_growth_action_items_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_growth_action_items_org_idempotency_key",
        ),
    )
    op.create_index(
        "ix_growth_action_items_org_status",
        "growth_action_items",
        ["organization_id", "status"],
    )

    op.create_table(
        "growth_action_dependencies",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depends_on_action_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "action_item_id <> depends_on_action_item_id",
            name=op.f("ck_growth_action_dependencies_not_self_dependency"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "action_item_id"],
            ["growth_action_items.organization_id", "growth_action_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "depends_on_action_item_id"],
            ["growth_action_items.organization_id", "growth_action_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_growth_action_dependencies")),
        sa.UniqueConstraint(
            "organization_id",
            "action_item_id",
            "depends_on_action_item_id",
            name="uq_growth_action_dependency_edge",
        ),
    )

    op.create_table(
        "growth_measurements",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome_classification", sa.String(length=32), nullable=False),
        sa.Column("metric_snapshot", _jsonb(), nullable=False),
        sa.Column("comparison", _jsonb(), nullable=False),
        sa.Column("source_references", _jsonb(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "window_days IN (0,7,14,28,56)",
            name=op.f("ck_growth_measurements_window_days"),
        ),
        sa.CheckConstraint(
            "outcome_classification IN ('baseline','pending','improved','no_material_change',"
            "'negative','insufficient_evidence')",
            name=op.f("ck_growth_measurements_outcome_classification"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "opportunity_id"],
            ["growth_opportunities.organization_id", "growth_opportunities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "action_plan_id"],
            ["growth_action_plans.organization_id", "growth_action_plans.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_growth_measurements")),
        sa.UniqueConstraint("organization_id", "id", name="uq_growth_measurements_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "opportunity_id",
            "window_days",
            name="uq_growth_measurement_window",
        ),
    )


def downgrade() -> None:
    op.drop_table("growth_measurements")
    op.drop_table("growth_action_dependencies")
    op.drop_index("ix_growth_action_items_org_status", table_name="growth_action_items")
    op.drop_table("growth_action_items")
    op.drop_table("growth_action_plans")
    op.drop_index("ix_growth_opportunities_org_status_priority", table_name="growth_opportunities")
    op.drop_table("growth_opportunities")
