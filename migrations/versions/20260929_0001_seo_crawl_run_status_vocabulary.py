"""Normalize legacy `seo_crawl_runs.status` values and close the vocabulary.

The crawl engine has only ever emitted `queued`, `running`, `success`,
`partial`, or `error` (see `apps.api.app.products.seo.crawl_engine`). An
earlier engine wrote `completed` for what is now `success`; those legacy
rows are normalized here, and a CHECK constraint closes the set going
forward so the column can never again drift out of sync with the code.

Revision ID: 20260929_0001
Revises: 20260925_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260929_0001"
down_revision: str | Sequence[str] | None = "20260925_0002"
branch_labels = depends_on = None

TABLE = "seo_crawl_runs"
CONSTRAINT = "seo_crawl_run_status"
STATUSES = ("queued", "running", "success", "partial", "error")


def _has_constraint(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == name for c in inspector.get_check_constraints(TABLE))


def upgrade() -> None:
    op.execute(f"UPDATE {TABLE} SET status = 'success' WHERE status = 'completed'")
    # `SEOCrawlRun.__table_args__` now declares this CHECK, so a database
    # whose `seo_crawl_runs` table was created after that model change
    # already has it (the founding migration instantiates the table from
    # the live model). Guard so this migration stays idempotent for both.
    if not _has_constraint(f"ck_{TABLE}_{CONSTRAINT}"):
        op.create_check_constraint(CONSTRAINT, TABLE, sa.text(f"status IN {STATUSES}"))


def downgrade() -> None:
    if _has_constraint(f"ck_{TABLE}_{CONSTRAINT}"):
        op.drop_constraint(CONSTRAINT, TABLE, type_="check")
