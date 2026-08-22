"""Index canonical Content opportunity source-reference lookup."""

from collections.abc import Sequence

from alembic import op

revision = "20260821_0002"
down_revision: str | Sequence[str] | None = "20260821_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_content_opportunities_org_source_reference",
        "content_opportunities",
        ["organization_id", "source_reference", "created_at", "id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_opportunities_org_source_reference",
        table_name="content_opportunities",
        if_exists=True,
    )
