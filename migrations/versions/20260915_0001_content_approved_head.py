"""Preserve the approved Content PR head across squash merge and recovery."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0001"
down_revision: str | Sequence[str] | None = "20260910_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.add_column("content_publications", sa.Column("approved_head_sha", sa.String(64)))
    op.execute(
        """UPDATE content_publications
        SET approved_head_sha = external_revision_id
        WHERE status IN ('pull_request_created', 'checks_running')
          AND external_revision_id IS NOT NULL"""
    )


def downgrade() -> None:
    op.drop_column("content_publications", "approved_head_sha")
