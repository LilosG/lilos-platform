"""Add safe_error_code to gbp_media."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260811_0002"
down_revision: str | Sequence[str] | None = "20260811_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("gbp_media")}
    if "safe_error_code" not in columns:
        op.add_column(
            "gbp_media",
            sa.Column("safe_error_code", sa.String(64), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("gbp_media", "safe_error_code")