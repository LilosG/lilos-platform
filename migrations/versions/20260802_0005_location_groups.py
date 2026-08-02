"""Create organization-scoped location groups and memberships.

Revision ID: 20260802_0005
Revises: 20260802_0004
Create Date: 2026-08-02

The migration adds only administrative selected-location grouping. It creates no configuration,
authorization, product, workflow, profile, hierarchy, or business-identity behavior. Immutable
audit evidence stores group and membership IDs as ordinary resource references, so downgrade does
not rewrite audit history.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0005"
down_revision: str | Sequence[str] | None = "20260802_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns(*, updated_at: bool) -> list[sa.Column[Any]]:
    columns: list[sa.Column[Any]] = [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]
    if updated_at:
        columns.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            )
        )
    return columns


def upgrade() -> None:
    op.create_table(
        "location_groups",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key", sa.String(63), nullable=False),
        sa.Column("description", sa.String(1_000)),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *_identity_columns(updated_at=True),
        sa.CheckConstraint("length(btrim(name)) BETWEEN 1 AND 120", name="name_length"),
        sa.CheckConstraint("char_length(key) BETWEEN 3 AND 63", name="key_length"),
        sa.CheckConstraint("key = lower(btrim(key))", name="key_normalized"),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'", name="key_format"),
        sa.CheckConstraint(
            "key NOT IN ('admin', 'api', 'internal', 'platform', 'public', "
            "'system', 'support', 'www')",
            name="key_not_reserved",
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(btrim(description)) BETWEEN 1 AND 1000",
            name="description_length",
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="location_group_status"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR "
            "(status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_location_groups_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_location_groups"),
        sa.UniqueConstraint("organization_id", "id", name="uq_location_groups_organization_id_id"),
        sa.UniqueConstraint(
            "organization_id", "key", name="uq_location_groups_organization_id_key"
        ),
    )
    op.create_index(
        "ix_location_groups_organization_created_at_id",
        "location_groups",
        ["organization_id", "created_at", "id"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_location_group_key_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.key IS DISTINCT FROM OLD.key THEN
                RAISE EXCEPTION 'location group key is immutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER location_groups_immutable_key
        BEFORE UPDATE OF key ON location_groups
        FOR EACH ROW
        EXECUTE FUNCTION prevent_location_group_key_change()
        """
    )

    op.create_table(
        "location_group_memberships",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        *_identity_columns(updated_at=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_lg_memberships_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_group_id"],
            ["location_groups.organization_id", "location_groups.id"],
            name="fk_lg_memberships_organization_group",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            name="fk_lg_memberships_organization_location",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_location_group_memberships"),
        sa.UniqueConstraint(
            "organization_id",
            "location_group_id",
            "location_id",
            name="uq_lg_memberships_organization_group_location",
        ),
    )
    op.create_index(
        "ix_location_group_memberships_organization_group_created_at_id",
        "location_group_memberships",
        ["organization_id", "location_group_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("location_group_memberships")
    op.drop_table("location_groups")
    op.execute("DROP FUNCTION prevent_location_group_key_change()")
