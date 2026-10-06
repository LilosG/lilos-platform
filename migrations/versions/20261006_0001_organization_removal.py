"""Record when an archived organization's data was permanently removed.

An archived organization keeps its data and keeps being synced. Removal is the second step:
a worker workflow deletes everything the organization owns and finally stamps ``removed_at``.
The ``organizations`` row itself is a tombstone and must stay, because ``audit_events`` is
append-only and its organization foreign keys are ``ON DELETE RESTRICT``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0001"
down_revision: str | Sequence[str] | None = "20261005_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECK = "ck_organizations_archived_timestamp_matches_status"
BEFORE = (
    "(status = 'archived' AND archived_at IS NOT NULL) OR "
    "(status <> 'archived' AND archived_at IS NULL)"
)
AFTER = f"({BEFORE}) AND (removed_at IS NULL OR status = 'archived')"


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("organizations")}
    if "removed_at" not in columns:
        op.add_column(
            "organizations",
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.drop_constraint(op.f(CHECK), "organizations", type_="check")
    op.create_check_constraint(op.f(CHECK), "organizations", AFTER)


def downgrade() -> None:
    op.drop_constraint(op.f(CHECK), "organizations", type_="check")
    op.create_check_constraint(op.f(CHECK), "organizations", BEFORE)
    op.drop_column("organizations", "removed_at")
