"""Add minimal Hermes run binding, scoped sessions, and event projection."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260824_0002"
down_revision: str | Sequence[str] | None = "20260824_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("skill_key", sa.String(length=128), nullable=False),
        sa.Column("namespace_hash", sa.String(length=64), nullable=False),
        sa.Column("hermes_session_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active','expired')", name=op.f("ck_agent_sessions_status")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_sessions")),
        sa.UniqueConstraint("hermes_session_key", name="uq_agent_sessions_hermes_key"),
        sa.UniqueConstraint("namespace_hash", name="uq_agent_sessions_namespace"),
        sa.UniqueConstraint("organization_id", "id", name="uq_agent_sessions_organization_id_id"),
    )
    op.create_table(
        "agent_runs",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_key", sa.String(length=128), nullable=False),
        sa.Column("skill_version", sa.Integer(), nullable=False),
        sa.Column("hermes_run_id", sa.String(length=128), nullable=True),
        sa.Column("hermes_session_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("provider_key", sa.String(length=64), server_default="hermes", nullable=False),
        sa.Column("model_key", sa.String(length=128), nullable=True),
        sa.Column("capability_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current_approval", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "source_references",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("final_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_microunits", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("safe_error_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','waiting_approval','stopping','completed',"
            "'cancelled','failed','capability_unavailable')",
            name=op.f("ck_agent_runs_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "agent_session_id"],
            ["agent_sessions.organization_id", "agent_sessions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["ai_execution_id"], ["ai_executions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
        sa.UniqueConstraint("hermes_run_id", name="uq_agent_runs_hermes_run"),
        sa.UniqueConstraint("organization_id", "id", name="uq_agent_runs_organization_id_id"),
        sa.UniqueConstraint("workflow_run_id", name="uq_agent_runs_workflow_run"),
    )
    op.create_index(
        "ix_agent_runs_scope_created",
        "agent_runs",
        ["organization_id", "location_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_agent_runs_active_session",
        "agent_runs",
        ["agent_session_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running','waiting_approval','stopping')"),
    )
    op.create_table(
        "agent_run_events",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "agent_run_id"],
            ["agent_runs.organization_id", "agent_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_run_events")),
        sa.UniqueConstraint("agent_run_id", "sequence", name="uq_agent_run_events_sequence"),
    )
    op.create_index(
        "ix_agent_run_events_org_expires",
        "agent_run_events",
        ["organization_id", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_run_events_run_created",
        "agent_run_events",
        ["agent_run_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_run_events_org_expires", table_name="agent_run_events")
    op.drop_index("ix_agent_run_events_run_created", table_name="agent_run_events")
    op.drop_table("agent_run_events")
    op.drop_index("uq_agent_runs_active_session", table_name="agent_runs")
    op.drop_index("ix_agent_runs_scope_created", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_table("agent_sessions")
