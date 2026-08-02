"""Create platform user profiles mapped to Supabase Auth subjects.

Revision ID: 20260802_0006
Revises: 20260802_0005
Create Date: 2026-08-02

No Supabase schema, token, session, membership, role, permission, or organization scope is stored.
Immutable audit evidence references platform users only through ordinary resource identifiers so a
controlled downgrade can preserve audit history.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0006"
down_revision: str | Sequence[str] | None = "20260802_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("auth_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("display_name", sa.String(200)),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True)),
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
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("status IN ('active', 'deactivated')", name="user_profile_status"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint(
            "(status = 'deactivated' AND deactivated_at IS NOT NULL) OR "
            "(status = 'active' AND deactivated_at IS NULL)",
            name="deactivated_timestamp_matches_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_profiles"),
        sa.UniqueConstraint("auth_user_id", name="uq_user_profiles_auth_user_id"),
    )
    op.execute(
        """
        CREATE FUNCTION prevent_user_profile_auth_subject_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.auth_user_id IS DISTINCT FROM OLD.auth_user_id THEN
                RAISE EXCEPTION 'user profile auth subject is immutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER user_profiles_immutable_auth_subject
        BEFORE UPDATE OF auth_user_id ON user_profiles
        FOR EACH ROW
        EXECUTE FUNCTION prevent_user_profile_auth_subject_change()
        """
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
    op.execute("DROP FUNCTION prevent_user_profile_auth_subject_change()")
