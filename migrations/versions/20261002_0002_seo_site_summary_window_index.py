"""Index site-summary Search Console observations by property and window.

The portfolio read looks up the newest exact-window ``site_summary`` of each mapped property.
Those rows are a tiny fraction of ``seo_search_observations`` (the rest are daily, top-query
and top-page rows), and without a partial index every lookup scanned the whole table.

Revision ID: 20261002_0002
Revises: 20261002_0001
"""

from collections.abc import Sequence

from alembic import op

revision = "20261002_0002"
down_revision: str | Sequence[str] | None = "20261002_0001"
branch_labels = depends_on = None

INDEX = "ix_seo_search_observations_site_summary_window"


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX} ON seo_search_observations "
        "(search_property_id, date_end DESC) "
        "WHERE (dimensions ->> 'observation_type') = 'site_summary' "
        "AND quality_status IN ('valid', 'zero')"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
