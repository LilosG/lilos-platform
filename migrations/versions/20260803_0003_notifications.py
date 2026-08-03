"""Create shared notification foundation."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.notifications.models import (
    NotificationDelivery,
    NotificationDeliveryAttempt,
    NotificationEvent,
    NotificationPreference,
    NotificationTemplate,
)

revision = "20260803_0003"
down_revision: str | Sequence[str] | None = "20260803_0002"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (
        NotificationTemplate,
        NotificationEvent,
        NotificationDelivery,
        NotificationDeliveryAttempt,
        NotificationPreference,
    )
)


def upgrade() -> None:
    for table in TABLES:
        table.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for table in reversed(TABLES):
        table.drop(bind=op.get_bind(), checkfirst=False)
