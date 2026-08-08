"""Create the analytics_properties table for GA4 property mappings."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.products.analytics.models import AnalyticsProperty

revision = "20260807_0001"
down_revision: str | Sequence[str] | None = "20260806_0002"
branch_labels = depends_on = None
TABLES = tuple(cast(Table, model.__table__) for model in (AnalyticsProperty,))


def upgrade() -> None:
    for table in TABLES:
        table.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for table in reversed(TABLES):
        table.drop(bind=op.get_bind(), checkfirst=False)
