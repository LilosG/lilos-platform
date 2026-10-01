"""Content briefs carry a typed target: an attributed existing page or a new page.

`target_reference` alone could not say whether a brief improves an attributed page or
proposes a new URL, so query-only SEO opportunities could never be drafted
(`CONTENT_SEO_TARGET_UNRESOLVED`). `target_kind` makes it explicit.

Backfill: a brief whose target is a proposed site path (starts with '/') becomes
`new_page`; every other brief stays `existing_page`, so placeholder briefs written before
attribution keep failing closed until `scripts.retire_stale_growth_work` retires them.

Revision ID: 20261001_0001
Revises: 20260930_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261001_0001"
down_revision: str | Sequence[str] | None = "20260930_0003"
branch_labels = depends_on = None

TABLE = "content_briefs"


def _has_constraint(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == name for c in inspector.get_check_constraints(TABLE))


def upgrade() -> None:
    # Migration 20260803_0009 creates the content tables from the live ORM models, so on
    # a fresh database the column and constraint may already exist; keep this idempotent.
    op.execute(
        f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS "
        "target_kind varchar(16) NOT NULL DEFAULT 'existing_page'"
    )
    op.execute(f"UPDATE {TABLE} SET target_kind = 'new_page' WHERE target_reference LIKE '/%'")
    if not _has_constraint("ck_content_briefs_target_kind"):
        # The metadata naming convention prefixes `ck_<table>_`, so pass the short name.
        op.create_check_constraint(
            "target_kind", TABLE, sa.text("target_kind IN ('existing_page','new_page')")
        )


def downgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS ck_content_briefs_target_kind")
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS target_kind")
