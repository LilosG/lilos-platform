# ruff: noqa: E501
"""Create reusable industries and nullable organization ownership.

Revision ID: 20260802_0003
Revises: 20260802_0002
Create Date: 2026-08-02

Creates the global industry registry and adds a nullable organization industry reference without
backfill. Existing organizations therefore remain compatible. Initial controlled records are
created only by the explicit audited seed command, not by this schema migration. Adding the
nullable organization column is additive; the foreign key briefly locks organizations. Downgrade
drops organization ownership before industries and otherwise retains organizations, locations,
and immutable audit history.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0003"
down_revision: str | Sequence[str] | None = "20260802_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDUSTRY_STATUSES = ("active", "deprecated", "archived")


def upgrade() -> None:
    op.create_table(
        "industries",
        sa.Column("key", sa.String(63), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column(
            "default_configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "default_risk_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "default_content_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
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
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint("char_length(key) BETWEEN 3 AND 63", name="key_length"),
        sa.CheckConstraint("key = lower(btrim(key))", name="key_normalized"),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'", name="key_format"),
        sa.CheckConstraint(
            "status IN ('active', 'deprecated', 'archived')", name="industry_status"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(default_configuration) = 'object'", name="configuration_object"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(default_risk_policy) = 'object'", name="risk_policy_object"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(default_content_policy) = 'object'", name="content_policy_object"
        ),
        sa.CheckConstraint(
            "octet_length(default_configuration::text) <= 16384", name="configuration_size"
        ),
        sa.CheckConstraint(
            "octet_length(default_risk_policy::text) <= 16384", name="risk_policy_size"
        ),
        sa.CheckConstraint(
            "octet_length(default_content_policy::text) <= 16384", name="content_policy_size"
        ),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR "
            "(status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_industries"),
        sa.UniqueConstraint("key", name="uq_industries_key"),
    )
    op.create_index("ix_industries_created_at_id", "industries", ["created_at", "id"])
    op.add_column(
        "organizations",
        sa.Column("industry_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_organizations_industry_id_industries",
        "organizations",
        "industries",
        ["industry_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE FUNCTION prevent_industry_key_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $industry_key_immutable$
        BEGIN
            IF NEW.key IS DISTINCT FROM OLD.key THEN
                RAISE EXCEPTION 'industry key is immutable' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $industry_key_immutable$
        """
    )
    op.execute(
        "CREATE TRIGGER industry_key_immutable BEFORE UPDATE ON industries "
        "FOR EACH ROW EXECUTE FUNCTION prevent_industry_key_change()"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_organizations_industry_id_industries", "organizations", type_="foreignkey"
    )
    op.drop_column("organizations", "industry_id")
    op.drop_table("industries")
    op.execute("DROP FUNCTION prevent_industry_key_change()")
