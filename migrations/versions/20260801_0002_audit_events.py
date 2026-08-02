"""Create the append-only audit-event foundation.

Revision ID: 20260801_0002
Revises: 20260801_0001
Create Date: 2026-08-01

Reason: provide durable shared audit evidence before tenant and product modules exist.
Tables affected: audit_events.
Constraints: UUID primary key, stable actor/result checks, bounded nonblank fields, JSON object
validation, and a restrictive self-reference for event chains.
Indexes: chronological, future organization scope, correlation, resource, and chain lookup.
Data backfill: none; this is a new empty table.
Application compatibility: additive and compatible with database-optional API startup.
Lock risk: a new empty table and support function require no existing-row rewrite.
Rollback: downgrade drops audit_events and its table-specific immutability function; recorded test
data is destructive by definition, so downgrade is intended only before production use or under an
approved recovery plan.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260801_0002"
down_revision: str | Sequence[str] | None = "20260801_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTOR_TYPES = ("user", "service", "workflow", "system", "external_provider")
RESULTS = ("succeeded", "failed", "denied", "partially_succeeded", "cancelled")


def _quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    """Create audit storage and reject ordinary mutation at the database boundary."""
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_display_reference", sa.String(length=200), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_key", sa.String(length=64), nullable=True),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("workflow_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent_summary", sa.String(length=256), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("approval_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            f"actor_type IN ({_quoted_values(ACTOR_TYPES)})",
            name="audit_actor_type",
        ),
        sa.CheckConstraint(
            f"result IN ({_quoted_values(RESULTS)})",
            name="audit_result",
        ),
        sa.CheckConstraint(
            "length(btrim(event_type)) > 0",
            name="event_type_not_blank",
        ),
        sa.CheckConstraint(
            "length(btrim(action)) > 0",
            name="action_not_blank",
        ),
        sa.CheckConstraint(
            "length(btrim(summary)) > 0",
            name="summary_not_blank",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'",
            name="metadata_is_object",
        ),
        sa.ForeignKeyConstraint(
            ["previous_audit_event_id"],
            ["audit_events.id"],
            name="fk_audit_events_previous_audit_event_id_audit_events",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_occurred_at_id",
        "audit_events",
        [sa.text("occurred_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_audit_events_organization_occurred_at_id",
        "audit_events",
        ["organization_id", sa.text("occurred_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_audit_events_correlation_id",
        "audit_events",
        ["correlation_id"],
    )
    op.create_index(
        "ix_audit_events_resource_occurred_at_id",
        "audit_events",
        ["resource_type", "resource_id", sa.text("occurred_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_audit_events_previous_audit_event_id",
        "audit_events",
        ["previous_audit_event_id"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_audit_events_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $audit_append_only$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only' USING ERRCODE = '55000';
        END;
        $audit_append_only$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_audit_events_mutation()
        """
    )


def downgrade() -> None:
    """Remove the audit foundation and return to the persistence baseline."""
    op.drop_table("audit_events")
    op.execute("DROP FUNCTION prevent_audit_events_mutation()")
