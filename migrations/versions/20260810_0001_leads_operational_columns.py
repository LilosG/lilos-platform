"""Repair Leads operational columns missing from existing databases.

Fresh databases receive these columns from the model-driven Leads table
creation migration. Databases that were upgraded before the model changed do
not, so this migration conditionally reconciles that historical schema drift.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260810_0001"
down_revision: str | Sequence[str] | None = "20260807_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("leads")}
    if "converted_value_cents" not in columns:
        op.add_column("leads", sa.Column("converted_value_cents", sa.Integer(), nullable=True))
    if "loss_reason" not in columns:
        op.add_column("leads", sa.Column("loss_reason", sa.String(length=500), nullable=True))


def downgrade() -> None:
    # These columns may predate this revision on databases created after the
    # model-driven table migration changed. Removing them would make downgrade
    # behavior depend on database creation date, so rollback is intentionally
    # non-destructive; the earlier Leads table downgrade remains authoritative.
    pass
