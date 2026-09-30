"""Add deterministic page-attribution state to SEO opportunities.

`seo_opportunities.page_id` was NULL for essentially every GSC/PageSpeed row
because opportunity generation excluded the `page_query` evidence that
attributes a query to a page. This adds the columns the rewritten
`SEOOrchestrationService` attribution logic writes: `attribution_state`
closes a deterministic set (`attributed`, `shared`, `query_only`,
`unresolved`), and `candidate_pages` carries the ranked page candidates for
`shared` (cannibalization) rows. Crawl-sourced technical-issue opportunities
always carried a real `page_id` (crawl evidence is page-scoped, not
attributed); those backfill to `attributed`. Every other existing row
already has `page_id IS NULL` and backfills to the column default,
`query_only` / `[]`; the next analysis run repairs it via
`SEOOrchestrationService._upsert_opportunity`, which now updates
`page_id`/`attribution_state`/`candidate_pages` on existing rows.

Revision ID: 20260929_0002
Revises: 20260929_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260929_0002"
down_revision: str | Sequence[str] | None = "20260929_0001"
branch_labels = depends_on = None

TABLE = "seo_opportunities"


def _has_constraint(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == name for c in inspector.get_check_constraints(TABLE))


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}
    if "attribution_state" not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                "attribution_state",
                sa.String(24),
                nullable=False,
                server_default="query_only",
            ),
        )
    if "candidate_pages" not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                "candidate_pages",
                postgresql.JSONB(),
                nullable=False,
                server_default="[]",
            ),
        )
    # A pre-existing row with a real page_id was crawl evidence (the only
    # source that ever set one before this migration) -- mark it attributed
    # so it starts consistent with the new CHECK below.
    op.execute(
        f"UPDATE {TABLE} SET attribution_state = 'attributed' "
        "WHERE page_id IS NOT NULL AND attribution_state <> 'attributed'"
    )
    if not _has_constraint("ck_seo_opportunities_attribution_state"):
        op.create_check_constraint(
            "attribution_state",
            TABLE,
            sa.text("attribution_state IN ('attributed','shared','query_only','unresolved')"),
        )
    if not _has_constraint("ck_seo_opportunities_attribution_state_page_consistent"):
        op.create_check_constraint(
            "attribution_state_page_consistent",
            TABLE,
            sa.text(
                "(attribution_state = 'attributed' AND page_id IS NOT NULL) OR "
                "(attribution_state <> 'attributed' AND page_id IS NULL)"
            ),
        )


def downgrade() -> None:
    if _has_constraint("ck_seo_opportunities_attribution_state_page_consistent"):
        op.drop_constraint("attribution_state_page_consistent", TABLE, type_="check")
    if _has_constraint("ck_seo_opportunities_attribution_state"):
        op.drop_constraint("attribution_state", TABLE, type_="check")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}
    if "candidate_pages" in columns:
        op.drop_column(TABLE, "candidate_pages")
    if "attribution_state" in columns:
        op.drop_column(TABLE, "attribution_state")
