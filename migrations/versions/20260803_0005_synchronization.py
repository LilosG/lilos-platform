"""Create provider synchronization foundation."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.synchronization.models import (
    ProviderStateSnapshot,
    SyncChangeIntent,
    SyncCheckpoint,
    SyncConflict,
    SyncDefinition,
    SyncRun,
)

revision = "20260803_0005"
down_revision: str | Sequence[str] | None = "20260803_0004"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (
        SyncDefinition,
        SyncRun,
        SyncCheckpoint,
        ProviderStateSnapshot,
        SyncChangeIntent,
        SyncConflict,
    )
)


def upgrade() -> None:
    for t in TABLES:
        t.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for t in reversed(TABLES):
        t.drop(bind=op.get_bind(), checkfirst=False)
