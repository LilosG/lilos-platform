"""Create the first GBP vertical slice."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.products.gbp.models import (
    GBPAccount,
    GBPLocation,
    GBPProfileChangeRevision,
    GBPProfileSnapshot,
    GBPPublication,
)

revision = "20260803_0006"
down_revision: str | Sequence[str] | None = "20260803_0005"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (GBPAccount, GBPLocation, GBPProfileSnapshot, GBPProfileChangeRevision, GBPPublication)
)


def upgrade() -> None:
    for t in TABLES:
        t.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for t in reversed(TABLES):
        t.drop(bind=op.get_bind(), checkfirst=False)
