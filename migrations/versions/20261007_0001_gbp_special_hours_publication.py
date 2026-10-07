"""Publish approved special hours to Google: a publication per write and per-date outcomes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261007_0001"
down_revision: str | Sequence[str] | None = "20261006_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "gbp_special_hours_publications"
STATUS_CHECK = "ck_gbp_special_hours_publications_status"  # the naming convention adds the prefix


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        op.create_table(
            TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
            sa.Column(
                "organization_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("gbp_location_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("sent_periods", postgresql.JSONB(), nullable=True),
            sa.Column("safe_error_code", sa.String(64), nullable=True),
            sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["organization_id", "gbp_location_id"],
                ["gbp_locations.organization_id", "gbp_locations.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "workflow_run_id"],
                ["workflow_runs.organization_id", "workflow_runs.id"],
                ondelete="RESTRICT",
            ),
            sa.UniqueConstraint(
                "organization_id",
                "idempotency_key",
                name="uq_gbp_special_hours_publication_idempotency",
            ),
            sa.UniqueConstraint("workflow_run_id", name="uq_gbp_special_hours_publication_run"),
            sa.CheckConstraint(
                "status IN ('reserved','dispatched','verified','failed','reconciliation_required')",
                name=op.f(STATUS_CHECK),
            ),
        )
    hours = {column["name"] for column in inspector.get_columns("gbp_special_hours")}
    if "publication_id" not in hours:
        op.add_column(
            "gbp_special_hours",
            sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if "safe_error_code" not in hours:
        op.add_column(
            "gbp_special_hours", sa.Column("safe_error_code", sa.String(64), nullable=True)
        )
    if "verified_at" not in hours:
        op.add_column(
            "gbp_special_hours",
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("gbp_special_hours", "verified_at")
    op.drop_column("gbp_special_hours", "safe_error_code")
    op.drop_column("gbp_special_hours", "publication_id")
    op.drop_table(TABLE)
