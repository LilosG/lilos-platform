"""Persist normalized, run-scoped SEO internal-link observations.

Revision ID: 20260925_0002
Revises: 20260925_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260925_0002"
down_revision: str | Sequence[str] | None = "20260925_0001"
branch_labels = depends_on = None

TABLE = "seo_internal_link_observations"
SOURCE_INDEX = "ix_seo_internal_links_org_website_run_source"
TARGET_INDEX = "ix_seo_internal_links_org_website_run_target"


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table(TABLE):
        raise RuntimeError(f"Unexpected pre-existing {TABLE} table")
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("website_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("crawl_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_page_id", postgresql.UUID(as_uuid=True)),
        sa.Column("raw_href", sa.Text(), nullable=False),
        sa.Column("normalized_target_url", sa.Text(), nullable=False),
        sa.Column("anchor_text", sa.Text()),
        sa.Column("nofollow", sa.Boolean(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("link_fingerprint", sa.String(64), nullable=False),
        sa.Column("mapping_state", sa.String(16), nullable=False),
        sa.Column("mapping_basis", sa.String(32)),
        sa.Column("resolver_version", sa.String(32), nullable=False),
        sa.Column("mapping_limitation", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "website_id", "crawl_run_id"],
            ["seo_crawl_runs.organization_id", "seo_crawl_runs.website_id", "seo_crawl_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "website_id", "source_page_id"],
            ["seo_pages.organization_id", "seo_pages.website_id", "seo_pages.id"],
            name="fk_seo_internal_links_source_page",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "website_id", "target_page_id"],
            ["seo_pages.organization_id", "seo_pages.website_id", "seo_pages.id"],
            name="fk_seo_internal_links_target_page",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "crawl_run_id",
            "source_page_id",
            "link_fingerprint",
            name="uq_seo_internal_link_run_source_fingerprint",
        ),
        sa.CheckConstraint("occurrence_count > 0", name="positive_occurrence_count"),
        sa.CheckConstraint(
            "(mapping_state = 'mapped' AND target_page_id IS NOT NULL) OR "
            "(mapping_state IN ('unmapped','ambiguous','unknown') AND target_page_id IS NULL)",
            name="target_mapping_consistent",
        ),
    )
    op.create_index(
        SOURCE_INDEX,
        TABLE,
        ["organization_id", "website_id", "crawl_run_id", "source_page_id"],
    )
    op.create_index(
        TARGET_INDEX,
        TABLE,
        ["organization_id", "website_id", "crawl_run_id", "target_page_id"],
    )


def downgrade() -> None:
    op.drop_index(TARGET_INDEX, table_name=TABLE)
    op.drop_index(SOURCE_INDEX, table_name=TABLE)
    op.drop_table(TABLE)
