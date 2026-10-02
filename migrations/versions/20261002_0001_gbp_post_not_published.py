"""GBP post publications can end `not_published` or `discarded`.

An ambiguous provider write is now re-read from Google automatically. When Google
shows no matching post, the publication is `not_published` and an operator either
reposts it (a new revision through the normal approval and write gate) or discards it.

Revision ID: 20261002_0001
Revises: 20261001_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261002_0001"
down_revision: str | Sequence[str] | None = "20261001_0002"
branch_labels = depends_on = None

TABLE = "gbp_post_publications"
CONSTRAINT = "ck_gbp_post_publications_status"
OLD = (
    "'reserved','scheduled','dispatched','verified','failed',"
    "'reconciliation_required','cancelled','expired'"
)
NEW = OLD + ",'not_published','discarded'"


def _replace(statuses: str) -> None:
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    # The metadata naming convention prefixes `ck_<table>_`, so pass the short name.
    op.create_check_constraint("status", TABLE, sa.text(f"status IN ({statuses})"))


def upgrade() -> None:
    _replace(NEW)


def downgrade() -> None:
    op.execute(
        f"UPDATE {TABLE} SET status = 'failed', "
        "safe_error_code = COALESCE(safe_error_code, 'POST_NOT_ON_GOOGLE') "
        "WHERE status IN ('not_published','discarded')"
    )
    _replace(OLD)
