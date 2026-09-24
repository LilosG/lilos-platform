"""Capture tenant-scoped page evidence for individual SEO crawl runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260924_0001"
down_revision: str | Sequence[str] | None = "20260920_0001"
branch_labels = depends_on = None
_CREATED_BY_THIS_REVISION = "lilos:20260924_0001"


def _ensure_composite_unique(table: str, name: str) -> None:
    columns = ["organization_id", "website_id", "id"]
    inspector = sa.inspect(op.get_bind())
    existing = next(
        (item for item in inspector.get_unique_constraints(table) if item["name"] == name),
        None,
    )
    if existing is not None:
        if existing["column_names"] != columns:
            raise RuntimeError(f"{name} exists with different columns")
        return
    if any(item["name"] == name for item in inspector.get_indexes(table)):
        raise RuntimeError(f"{name} is an index, not the required unique constraint")
    op.create_unique_constraint(name, table, columns)
    op.execute(sa.text(f"COMMENT ON CONSTRAINT {name} ON {table} IS '{_CREATED_BY_THIS_REVISION}'"))


def _drop_if_created_here(table: str, name: str) -> None:
    description = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT obj_description(c.oid, 'pg_constraint') "
                "FROM pg_constraint AS c "
                "JOIN pg_class AS t ON t.oid = c.conrelid "
                "JOIN pg_namespace AS n ON n.oid = t.relnamespace "
                "WHERE n.nspname = current_schema() AND t.relname = :table AND c.conname = :name"
            ),
            {"table": table, "name": name},
        )
        .scalar_one_or_none()
    )
    if description == _CREATED_BY_THIS_REVISION:
        op.drop_constraint(name, table, type_="unique")


def upgrade() -> None:
    _ensure_composite_unique("seo_pages", "uq_seo_pages_org_website_id")
    _ensure_composite_unique("seo_crawl_runs", "uq_seo_crawl_runs_org_website_id")
    op.create_table(
        "seo_crawl_page_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("website_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("crawl_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("observed_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("normalization_reasons", postgresql.JSONB(), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("content_type", sa.String(255)),
        sa.Column("title", sa.String(2000)),
        sa.Column("meta_description", sa.String(2000)),
        sa.Column("h1", sa.String(2000)),
        sa.Column("robots_directives", postgresql.JSONB(), nullable=False),
        sa.Column("internal_links", postgresql.JSONB(), nullable=False),
        sa.Column("external_links", postgresql.JSONB(), nullable=False),
        sa.Column("word_count", sa.Integer()),
        sa.Column("structured_data_present", sa.Boolean(), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("indexability", sa.String(24), nullable=False),
        sa.Column("technical_issues", postgresql.JSONB(), nullable=False),
        sa.Column("crawl_depth", sa.Integer()),
        sa.Column("redirect_destination", sa.Text()),
        sa.Column("quality_status", sa.String(24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "website_id", "crawl_run_id"],
            ["seo_crawl_runs.organization_id", "seo_crawl_runs.website_id", "seo_crawl_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "website_id", "page_id"],
            ["seo_pages.organization_id", "seo_pages.website_id", "seo_pages.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "crawl_run_id", "normalized_url", name="uq_seo_crawl_page_observation_run_url"
        ),
    )
    op.create_index(
        "ix_seo_crawl_page_observations_crawl_run_id",
        "seo_crawl_page_observations",
        ["crawl_run_id"],
    )
    op.create_index(
        "ix_seo_crawl_page_observations_org_run",
        "seo_crawl_page_observations",
        ["organization_id", "crawl_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_seo_crawl_page_observations_org_run", table_name="seo_crawl_page_observations"
    )
    op.drop_index(
        "ix_seo_crawl_page_observations_crawl_run_id", table_name="seo_crawl_page_observations"
    )
    op.drop_table("seo_crawl_page_observations")
    _drop_if_created_here("seo_crawl_runs", "uq_seo_crawl_runs_org_website_id")
    _drop_if_created_here("seo_pages", "uq_seo_pages_org_website_id")
