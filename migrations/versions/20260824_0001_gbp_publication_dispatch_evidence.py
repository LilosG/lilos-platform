"""Add durable GBP post dispatch and recovery evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260824_0001"
down_revision: str | Sequence[str] | None = "20260821_0002"
branch_labels = depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("gbp_post_publications")}
    if "dispatched_at" not in columns:
        op.add_column(
            "gbp_post_publications",
            sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "safe_error_code" not in columns:
        op.add_column(
            "gbp_post_publications",
            sa.Column("safe_error_code", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("gbp_post_publications", "safe_error_code")
    op.drop_column("gbp_post_publications", "dispatched_at")
