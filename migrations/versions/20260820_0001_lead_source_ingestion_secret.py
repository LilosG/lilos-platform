# ruff: noqa: E501
"""Create lead_source_ingestion_credentials — system-scoped machine auth.

This table is deliberately NOT subject to row-level security.  It exists
solely to resolve a machine credential (ingestion_key + secret) into an
(organization_id, lead_source_id) pair before tenant context is established.

Once the tenant is known, the normal RLS-protected LeadSource row is loaded
and the standard intake path executes under full tenant isolation.

The ingestion_key and ingestion_secret_hash columns are removed from
lead_sources — authentication data belongs in the credential registry,
not in tenant business data.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260820_0001"
down_revision: str | Sequence[str] | None = "20260819_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector_columns = {c["name"] for c in sa.inspect(bind).get_columns("lead_sources")}

    # 1. Create the system-scoped credential table (no RLS).
    op.create_table(
        "lead_source_ingestion_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "ingestion_key",
            sa.String(length=64),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "ingestion_key",
            name="uq_ingestion_credential_key",
        ),
        sa.Column("lead_source_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("secret_hash", sa.String(length=256), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["lead_source_id"],
            ["lead_sources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('active','revoked')",
            name="ck_ingestion_credential_status",
        ),
    )

    # 2. Remove ingestion columns from lead_sources (auth data belongs in
    #    the credential registry, not in tenant business data).
    if "ingestion_secret_hash" in inspector_columns:
        op.drop_column("lead_sources", "ingestion_secret_hash")
    if "ingestion_key" in inspector_columns:
        op.drop_constraint("uq_lead_sources_ingestion_key", "lead_sources", type_="unique")
        op.drop_column("lead_sources", "ingestion_key")


def downgrade() -> None:
    op.drop_table("lead_source_ingestion_credentials")

    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("lead_sources")}
    if "ingestion_key" not in columns:
        op.add_column(
            "lead_sources",
            sa.Column("ingestion_key", sa.String(length=64), nullable=True),
        )
        op.create_unique_constraint(
            "uq_lead_sources_ingestion_key", "lead_sources", ["ingestion_key"]
        )
    if "ingestion_secret_hash" not in columns:
        op.add_column(
            "lead_sources",
            sa.Column("ingestion_secret_hash", sa.String(length=256), nullable=True),
        )
