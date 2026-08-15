"""Add crawl-engine observation columns to SEO page and crawl run records.

Expand-and-contract: every new column is nullable (or carries a safe default)
so existing rows remain valid and no data backfill is required. The crawl
engine populates these fields for new crawl runs; legacy rows simply leave
them null.

Uses ``IF NOT EXISTS`` so the migration is safe to re-run after the
model-driven table creation in ``20260803_0010`` has already included
these columns on fresh databases.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import TypeEngine

revision = "20260813_0001"
down_revision: str | Sequence[str] | None = "20260812_0002"
branch_labels = depends_on = None

_PAGE_COLUMNS: list[tuple[str, TypeEngine[Any]]] = [
    ("content_type", sa.String(255)),
    ("title", sa.String(2000)),
    ("meta_description", sa.String(2000)),
    ("h1", sa.String(2000)),
    ("word_count", sa.Integer()),
    ("content_hash", sa.String(64)),
    ("crawl_depth", sa.Integer()),
    ("redirect_destination", sa.String(2000)),
]

_PAGE_COLUMN_NAMES: tuple[str, ...] = (
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
)

_CRAWL_RUN_COLUMNS: list[tuple[str, TypeEngine[Any]]] = [
    ("max_depth", sa.Integer()),
    ("crawl_delay_seconds", sa.Float()),
    ("stop_reason", sa.String(500)),
    ("started_at", sa.DateTime(timezone=True)),
]

_CRAWL_RUN_COLUMN_NAMES: tuple[str, ...] = tuple(name for name, _ in _CRAWL_RUN_COLUMNS)


def upgrade() -> None:
    for col_name, col_type in _PAGE_COLUMNS:
        _add_column_if_not_exists("seo_pages", col_name, col_type)
    op.execute(
        sa.text(
            "ALTER TABLE seo_pages ADD COLUMN IF NOT EXISTS robots_directives "
            "JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seo_pages ADD COLUMN IF NOT EXISTS internal_links "
            "JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seo_pages ADD COLUMN IF NOT EXISTS external_links "
            "JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seo_pages ADD COLUMN IF NOT EXISTS structured_data_present "
            "BOOLEAN NOT NULL DEFAULT false"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seo_pages ADD COLUMN IF NOT EXISTS technical_issues "
            "JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
    )

    for col_name, col_type in _CRAWL_RUN_COLUMNS:
        _add_column_if_not_exists("seo_crawl_runs", col_name, col_type)


def _add_column_if_not_exists(
    table_name: str,
    col_name: str,
    col_type: TypeEngine[Any],
) -> None:
    """Add ``col_name`` only when it does not already exist on ``table_name``."""
    dialect = op.get_context().dialect
    compiled_type = col_type.compile(dialect=dialect)
    op.execute(
        sa.text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {compiled_type}")
    )


def downgrade() -> None:
    for col_name in _PAGE_COLUMN_NAMES:
        op.drop_column("seo_pages", col_name)
    for col_name in _CRAWL_RUN_COLUMN_NAMES:
        op.drop_column("seo_crawl_runs", col_name)
