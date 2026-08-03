"""Create organization memberships, invitations, and immutable access catalogs.

Revision ID: 20260802_0007
Revises: 20260802_0006
Create Date: 2026-08-02

This migration stores authorization-domain data but does not enforce route authorization or RLS.
Invitation plaintext tokens are never persisted. Audit evidence retains identifiers as ordinary
metadata/resource references, allowing downgrade without rewriting immutable history.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0007"
down_revision: str | Sequence[str] | None = "20260802_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps(*, updated: bool = True) -> list[sa.Column[Any]]:
    result = [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        )
    ]
    if updated:
        result.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            )
        )
    return result


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(63), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *timestamps(),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("status = 'active'", name="role_status_active"),
        sa.CheckConstraint("is_system", name="role_system_only"),
        sa.CheckConstraint("version = 1", name="role_version_immutable"),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("key", name="uq_roles_key"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("resource", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        *timestamps(updated=False),
        sa.CheckConstraint(
            "key ~ '^[a-z][a-z0-9_]*(?:\\.[a-z][a-z0-9_]*)+$'",
            name="permission_key_format",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
        sa.UniqueConstraint("key", name="uq_permissions_key"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(updated=False),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_role_permissions_role_id_roles", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name="fk_role_permissions_permission_id_permissions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True)),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("expired_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "membership_type IN ('internal','client','partner','support')", name="membership_type"
        ),
        sa.CheckConstraint(
            "status IN ('invited','active','suspended','revoked','expired')",
            name="membership_status",
        ),
        sa.CheckConstraint("version >= 1", name="membership_version_positive"),
        sa.CheckConstraint(
            "(status IN ('active','suspended') AND activated_at IS NOT NULL) OR "
            "(status IN ('invited','expired') AND activated_at IS NULL) OR "
            "status='revoked'",
            name="membership_activated_timestamp_consistent",
        ),
        sa.CheckConstraint(
            "(status='suspended') = (suspended_at IS NOT NULL)",
            name="membership_suspended_timestamp_consistent",
        ),
        sa.CheckConstraint(
            "(status='revoked') = (revoked_at IS NOT NULL)",
            name="membership_revoked_timestamp_consistent",
        ),
        sa.CheckConstraint(
            "(status='expired') = (expired_at IS NOT NULL)",
            name="membership_expired_timestamp_consistent",
        ),
        sa.CheckConstraint(
            "status NOT IN ('invited','expired') OR invited_at IS NOT NULL",
            name="membership_invited_timestamp_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_memberships_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_profile_id"],
            ["user_profiles.id"],
            name="fk_organization_memberships_user_profile_id_user_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_memberships"),
        sa.UniqueConstraint(
            "organization_id", "user_profile_id", name="uq_memberships_organization_user"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_memberships_organization_id_id"),
    )
    op.create_index(
        "ix_memberships_organization_created_id",
        "organization_memberships",
        ["organization_id", "created_at", "id"],
    )
    op.create_table(
        "organization_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("token_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_user_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accepted_by_user_profile_id", postgresql.UUID(as_uuid=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','accepted','cancelled','expired')", name="invitation_status"
        ),
        sa.CheckConstraint("version >= 1", name="invitation_version_positive"),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="invitation_token_hash_sha256"),
        sa.CheckConstraint(
            "(status='accepted') = (accepted_at IS NOT NULL)",
            name="invitation_accepted_timestamp_consistent",
        ),
        sa.CheckConstraint(
            "(status='accepted') = (accepted_by_user_profile_id IS NOT NULL)",
            name="invitation_accepted_actor_consistent",
        ),
        sa.CheckConstraint(
            "(status='cancelled') = (cancelled_at IS NOT NULL)",
            name="invitation_cancelled_timestamp_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_invitations_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            name="fk_invitations_organization_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_profile_id"],
            ["user_profiles.id"],
            name="fk_invitations_invited_by_user_profile",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_profile_id"],
            ["user_profiles.id"],
            name="fk_invitations_accepted_by_user_profile",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_invitations"),
        sa.UniqueConstraint("membership_id", name="uq_invitations_membership_id"),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
        sa.UniqueConstraint("organization_id", "id", name="uq_invitations_organization_id_id"),
    )
    op.create_index(
        "ix_invitations_organization_created_id",
        "organization_invitations",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "uq_invitations_pending_organization_email",
        "organization_invitations",
        ["organization_id", "normalized_email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    _create_scoped_table("membership_role_assignments", "role_id", "roles", "id")
    _create_scoped_table("membership_permission_denies", "permission_id", "permissions", "id")
    op.execute("""
        CREATE FUNCTION prevent_access_identity_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_TABLE_NAME = 'organization_memberships'
             AND NEW.membership_type IS DISTINCT FROM OLD.membership_type THEN
            RAISE EXCEPTION 'membership type is immutable' USING ERRCODE='23514';
          END IF;
          IF TG_TABLE_NAME IN ('roles','permissions') AND NEW.key IS DISTINCT FROM OLD.key THEN
            RAISE EXCEPTION 'catalog key is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$
    """)
    op.execute(
        "CREATE TRIGGER organization_memberships_immutable_type "
        "BEFORE UPDATE OF membership_type ON organization_memberships FOR EACH ROW "
        "EXECUTE FUNCTION prevent_access_identity_change()"
    )
    op.execute(
        "CREATE TRIGGER roles_immutable_key BEFORE UPDATE OF key ON roles "
        "FOR EACH ROW EXECUTE FUNCTION prevent_access_identity_change()"
    )
    op.execute(
        "CREATE TRIGGER permissions_immutable_key BEFORE UPDATE OF key ON permissions "
        "FOR EACH ROW EXECUTE FUNCTION prevent_access_identity_change()"
    )


def _create_scoped_table(
    table: str, target_column: str, target_table: str, target_key: str
) -> None:
    singular = "role_assignment" if table == "membership_role_assignments" else "permission_deny"
    op.create_table(
        table,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(target_column, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True)),
        *timestamps(updated=False),
        sa.CheckConstraint(
            "scope_type IN ('organization','location')", name=f"{singular}_scope_type"
        ),
        sa.CheckConstraint(
            "(scope_type='organization' AND location_id IS NULL) OR "
            "(scope_type='location' AND location_id IS NOT NULL)",
            name=f"{singular}_scope_identity_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=f"fk_{table}_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            name=f"fk_{table}_organization_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            name=f"fk_{table}_organization_location",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [target_column],
            [f"{target_table}.{target_key}"],
            name=f"fk_{table}_{target_column}_{target_table}",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
    )
    prefix = "role_assignments" if table == "membership_role_assignments" else "permission_denies"
    op.create_index(
        f"uq_{prefix}_organization_scope",
        table,
        ["organization_id", "membership_id", target_column],
        unique=True,
        postgresql_where=sa.text("location_id IS NULL"),
    )
    op.create_index(
        f"uq_{prefix}_location_scope",
        table,
        ["organization_id", "membership_id", target_column, "location_id"],
        unique=True,
        postgresql_where=sa.text("location_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("membership_permission_denies")
    op.drop_table("membership_role_assignments")
    op.drop_table("role_permissions")
    op.drop_table("organization_invitations")
    op.execute("DROP TRIGGER organization_memberships_immutable_type ON organization_memberships")
    op.drop_table("organization_memberships")
    op.execute("DROP TRIGGER permissions_immutable_key ON permissions")
    op.drop_table("permissions")
    op.execute("DROP TRIGGER roles_immutable_key ON roles")
    op.drop_table("roles")
    op.execute("DROP FUNCTION prevent_access_identity_change()")
