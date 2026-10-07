"""Keep the operator's original prompt on the content brief that came from it."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261008_0001"
down_revision: str | Sequence[str] | None = "20261007_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "content_briefs"
COLUMN = "source_prompt"


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    if COLUMN not in _columns():
        op.add_column(TABLE, sa.Column(COLUMN, sa.Text(), nullable=True))


def downgrade() -> None:
    if COLUMN in _columns():
        op.drop_column(TABLE, COLUMN)
