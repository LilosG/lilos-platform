"""Add crawl-engine observation columns to SEO page and crawl run records.

Expand-and-contract: every new column is nullable (or carries a safe default)
so existing rows remain valid and no data backfill is required. The crawl
engine populates these fields for new crawl runs; legacy rows simply leave
them null.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260813_0001"
down_revision: str | Sequence[str] | None = "20260812_0002"
branch_labels = depends_on = None


def upgrade() -> None:
    op.add_column("seo_pages", sa.Column("content_type", sa.String(255), nullable=True))
    op.add_column("seo_pages", sa.Column("title", sa.String(2000), nullable=True))
    op.add_column("seo_pages", sa.Column("meta_description", sa.String(2000), nullable=True))
    op.add_column("seo_pages", sa.Column("h1", sa.String(2000), nullable=True))
    op.add_column(
        "seo_pages",
        sa.Column(
            "robots_directives", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "seo_pages",
        sa.Column(
            "internal_links", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "seo_pages",
        sa.Column(
            "external_links", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column("seo_pages", sa.Column("word_count", sa.Integer(), nullable=True))
    op.add_column(
        "seo_pages",
        sa.Column("structured_data_present", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("seo_pages", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column(
        "seo_pages",
        sa.Column(
            "technical_issues", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column("seo_pages", sa.Column("crawl_depth", sa.Integer(), nullable=True))
    op.add_column("seo_pages", sa.Column("redirect_destination", sa.String(2000), nullable=True))

    op.add_column("seo_crawl_runs", sa.Column("max_depth", sa.Integer(), nullable=True))
    op.add_column("seo_crawl_runs", sa.Column("crawl_delay_seconds", sa.Float(), nullable=True))
    op.add_column("seo_crawl_runs", sa.Column("stop_reason", sa.String(500), nullable=True))
    op.add_column(
        "seo_crawl_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    for column in (
        "content_type",
        "title",
        "meta_description",
        "h1",
        "robots_directives",
        "internal_links",
        "external_links",
        "word_count",
        "structured_data_present",
        "content_hash",
        "technical_issues",
        "crawl_depth",
        "redirect_destination",
    ):
        op.drop_column("seo_pages", column)

    for column in ("max_depth", "crawl_delay_seconds", "stop_reason", "started_at"):
        op.drop_column("seo_crawl_runs", column)
