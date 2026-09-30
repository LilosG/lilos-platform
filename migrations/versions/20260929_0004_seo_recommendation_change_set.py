"""Add structured change-set columns to SEO recommendation revisions.

A recommendation used to carry only free prose (`proposed_action`). This
adds `change_set` (the exact `SiteChangeSet` a human approves -- page,
field, current value read from the live repo, proposed value) and
`change_set_fingerprint` (recorded at approval, re-derived and checked at
execution so what was approved is provably what executes). Both are
nullable: not every recommendation targets a governed site edit through the
new executor (technical crawl-issue recommendations still verify by
re-crawling, per SEOService.create_implementation_task).

Revision ID: 20260929_0004
Revises: 20260929_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260929_0004"
down_revision: str | Sequence[str] | None = "20260929_0003"
branch_labels = depends_on = None

TABLE = "seo_recommendation_revisions"


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}
    if "change_set" not in columns:
        op.add_column(TABLE, sa.Column("change_set", postgresql.JSONB(), nullable=True))
    if "change_set_fingerprint" not in columns:
        op.add_column(TABLE, sa.Column("change_set_fingerprint", sa.String(64), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}
    if "change_set_fingerprint" in columns:
        op.drop_column(TABLE, "change_set_fingerprint")
    if "change_set" in columns:
        op.drop_column(TABLE, "change_set")
