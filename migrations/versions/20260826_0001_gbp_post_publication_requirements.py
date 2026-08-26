"""Persist versioned delivery requirements on approved GBP post revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260826_0001"
down_revision: str | Sequence[str] | None = "20260824_0002"
branch_labels = depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("gbp_post_revisions")}
    if "publication_requirements" not in columns:
        op.add_column(
            "gbp_post_revisions",
            sa.Column(
                "publication_requirements",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("gbp_post_revisions")}
    if "publication_requirements" in columns:
        op.drop_column("gbp_post_revisions", "publication_requirements")
