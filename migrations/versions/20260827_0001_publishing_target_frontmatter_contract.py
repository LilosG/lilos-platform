"""Store each publishing target's Astro frontmatter contract.

Client Astro collections agree on `title` and `description` and diverge on almost
everything else: the date field is `date`, `pubDate` or a required `publishDate`
depending on the repository, two clients require a `category` enum, one constrains
`serviceAreas` to an enum, and one names FAQ keys `q`/`a` rather than
`question`/`answer`. Emitting a field name the collection schema does not declare
fails `astro build` and breaks that client's deployment, so the contract has to be
recorded per target rather than assumed in code.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260827_0001"
down_revision: str | Sequence[str] | None = "20260826_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("publishing_targets")}
    if "frontmatter_contract" not in columns:
        op.add_column(
            "publishing_targets",
            sa.Column(
                "frontmatter_contract",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("publishing_targets")}
    if "frontmatter_contract" in columns:
        op.drop_column("publishing_targets", "frontmatter_contract")
