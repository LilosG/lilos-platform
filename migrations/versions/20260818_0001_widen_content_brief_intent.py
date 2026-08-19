# ruff: noqa: E501
"""Widen content_briefs.intent from varchar(100) to varchar(500).

Supports practical content-goal descriptions up to 500 characters.
"""

from collections.abc import Sequence

from alembic import op

revision = "20260818_0001"
down_revision: str | Sequence[str] | None = "20260817_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE content_briefs ALTER COLUMN intent TYPE varchar(500)")


def downgrade() -> None:
    op.execute("ALTER TABLE content_briefs ALTER COLUMN intent TYPE varchar(100)")
