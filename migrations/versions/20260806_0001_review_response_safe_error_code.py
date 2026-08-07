"""Add safe_error_code to review_response_revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260806_0001"
down_revision: str | Sequence[str] | None = "20260805_0002"
branch_labels = depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("review_response_revisions")}
    if "safe_error_code" not in columns:
        op.add_column(
            "review_response_revisions",
            sa.Column("safe_error_code", sa.String(128), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("review_response_revisions", "safe_error_code")
