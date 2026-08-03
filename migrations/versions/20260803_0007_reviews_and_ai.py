"""Create shared AI gateway records and Reviews product."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.products.reviews.models import (
    Review,
    ReviewEscalation,
    ReviewResponseRevision,
    ReviewRevision,
    ReviewRiskFlag,
)

revision = "20260803_0007"
down_revision: str | Sequence[str] | None = "20260803_0006"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (
        AITaskDefinition,
        AIExecution,
        Review,
        ReviewRevision,
        ReviewRiskFlag,
        ReviewResponseRevision,
        ReviewEscalation,
    )
)


def upgrade() -> None:
    for t in TABLES:
        t.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for t in reversed(TABLES):
        t.drop(bind=op.get_bind(), checkfirst=False)
