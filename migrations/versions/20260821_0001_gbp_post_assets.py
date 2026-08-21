"""Add selected media assets for governed GBP post revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260821_0001"
down_revision: str | Sequence[str] | None = "20260820_0002"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "gbp_post_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.String(length=1000), nullable=False),
        sa.Column("provider_fetch_url", sa.String(length=4000), nullable=False),
        sa.Column("metadata_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="selected", nullable=False),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "post_revision_id"],
            ["gbp_post_revisions.organization_id", "gbp_post_revisions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_gbp_post_assets_org_id"),
        sa.UniqueConstraint("post_revision_id", name="uq_gbp_post_asset_revision"),
    )


def downgrade() -> None:
    op.drop_table("gbp_post_assets")
