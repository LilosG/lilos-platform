"""Persist provider Local Post truth for read-side reconciliation."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.products.gbp.operations_models import GBPProviderPost

revision = "20260811_0001"
down_revision: str | Sequence[str] | None = "20260810_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    table = cast(Table, GBPProviderPost.__table__)
    table.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    table = cast(Table, GBPProviderPost.__table__)
    table.drop(bind=op.get_bind(), checkfirst=False)
