"""Add cross-product growth initiatives, actions, and measured outcomes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260910_0001"
down_revision: str | Sequence[str] | None = "20260827_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "growth_initiatives",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("planner_agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("objective", sa.String(length=2000), nullable=False),
        sa.Column("rationale", sa.String(length=5000), nullable=False),
        sa.Column("source_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=8, scale=6), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="proposed", nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("priority_score BETWEEN 0 AND 100", name="ck_growth_initiatives_priority_score"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_growth_initiatives_confidence"),
        sa.CheckConstraint(
            "status IN ('proposed','approved','rejected','executing','completed','cancelled')",
            name="ck_growth_initiatives_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "planner_agent_run_id"],
            ["agent_runs.organization_id", "agent_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["user_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_growth_initiatives_org_id"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_growth_initiatives_idempotency"
        ),
    )
    op.create_index(
        "ix_growth_initiatives_scope_status",
        "growth_initiatives",
        ["organization_id", "location_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "growth_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("initiative_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_key", sa.String(length=128), nullable=False),
        sa.Column("product_key", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_reference", sa.String(length=1000), nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("executor_workflow_key", sa.String(length=128), nullable=True),
        sa.Column("dependency_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_result_hypothesis", sa.String(length=2000), nullable=False),
        sa.Column("verification_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk", sa.String(length=16), nullable=False),
        sa.Column("effort", sa.String(length=16), nullable=False),
        sa.Column("approval_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="proposed", nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_reference", sa.String(length=500), nullable=True),
        sa.Column("safe_error_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_growth_actions_position_nonnegative"),
        sa.CheckConstraint(
            "execution_mode IN ('workflow','manual','monitor')",
            name="ck_growth_actions_execution_mode",
        ),
        sa.CheckConstraint(
            "(execution_mode = 'workflow' AND executor_workflow_key IS NOT NULL) OR "
            "(execution_mode <> 'workflow' AND executor_workflow_key IS NULL)",
            name="ck_growth_actions_executor_binding",
        ),
        sa.CheckConstraint("risk IN ('low','medium','high')", name="ck_growth_actions_risk"),
        sa.CheckConstraint("effort IN ('low','medium','high')", name="ck_growth_actions_effort"),
        sa.CheckConstraint(
            "status IN ('proposed','approved','queued','running','waiting_approval','completed','failed','skipped','cancelled')",
            name="ck_growth_actions_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "initiative_id"],
            ["growth_initiatives.organization_id", "growth_initiatives.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_growth_actions_org_id"),
        sa.UniqueConstraint("initiative_id", "action_key", name="uq_growth_actions_plan_key"),
    )
    op.create_index(
        "ix_growth_actions_initiative_position",
        "growth_actions",
        ["initiative_id", "position"],
        unique=False,
    )
    op.create_index(
        "ix_growth_actions_scope_status",
        "growth_actions",
        ["organization_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "growth_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classification", sa.String(length=24), nullable=False),
        sa.Column("baseline", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("measurement", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "classification IN ('improved','unchanged','regressed','inconclusive')",
            name="ck_growth_outcomes_classification",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "action_id"],
            ["growth_actions.organization_id", "growth_actions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_growth_outcomes_action_observed",
        "growth_outcomes",
        ["action_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_growth_outcomes_action_observed", table_name="growth_outcomes")
    op.drop_table("growth_outcomes")
    op.drop_index("ix_growth_actions_scope_status", table_name="growth_actions")
    op.drop_index("ix_growth_actions_initiative_position", table_name="growth_actions")
    op.drop_table("growth_actions")
    op.drop_index("ix_growth_initiatives_scope_status", table_name="growth_initiatives")
    op.drop_table("growth_initiatives")
