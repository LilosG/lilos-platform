"""Widen SEO page URL columns from varchar(2000) to unbounded text.

Packet 9D: a live crawl of ``wheylandelectric.com`` aborted with
``StringDataRightTruncationError`` — the crawler extracts per-page signals that
exceed ``varchar(2000)`` (the ``h1`` signal alone reaches ~9,000 characters),
and one oversized value aborted the whole crawl so zero pages persisted.

The seven offending columns split into two categories with different fixes:

* Content columns (``title``, ``meta_description``, ``h1``) stay ``varchar(2000)``
  and are truncated at ingest (see ``crawl_engine.MAX_CONTENT_LENGTH``) with an
  explicit ``[truncated]`` marker recorded in both the value and the page's
  ``technical_issues``. No schema change is required for these.

* URL columns (``normalized_url``, ``observed_url``, ``canonical_url``,
  ``redirect_destination``) are widened to ``text`` here. Browsers and servers
  legitimately produce URLs beyond 2000 characters, and truncating a URL would
  silently corrupt a reference the platform uses for deduplication and
  traversal. The crawler enforces a documented maximum instead (see
  ``crawl_engine.MAX_URL_LENGTH`` = 2048) and records an over-long page as
  skipped with a reason rather than persisting a corrupt value.

Expand (this migration): ``ALTER COLUMN ... TYPE text`` is non-destructive.
``text`` is a strict superset of ``varchar(2000)``, so every existing row
remains valid and no backfill is required.

``uq_seo_page_normalized_url`` (btree on ``website_id``, ``normalized_url``):
PostgreSQL limits a btree index entry to roughly one third of an 8192-byte page
(~2704 bytes). ``normalized_url`` is capped at 2048 characters (ASCII after
normalization) plus the 16-byte ``website_id`` and index-tuple overhead, which
stays well under that limit. Verified by inserting a 2048-character URL through
the live index.

Contract (deferred, documented): no separate contraction step is needed because
``text`` already carries no length ceiling.

Rollback (downgrade): restore ``varchar(2000)``. This succeeds only while no
stored URL exceeds 2000 characters. Because the crawler ceiling is 2048, a
downgrade fails loudly (Postgres raises) if a 2001-2048 character URL was
persisted during the expanded window rather than silently truncating data.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0001"
down_revision: str | Sequence[str] | None = "20260815_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_URL_COLUMNS: tuple[str, ...] = (
    "normalized_url",
    "observed_url",
    "canonical_url",
    "redirect_destination",
)


def upgrade() -> None:
    for col in _URL_COLUMNS:
        op.execute(sa.text(f"ALTER TABLE seo_pages ALTER COLUMN {col} TYPE text"))


def downgrade() -> None:
    for col in _URL_COLUMNS:
        op.execute(sa.text(f"ALTER TABLE seo_pages ALTER COLUMN {col} TYPE varchar(2000)"))
