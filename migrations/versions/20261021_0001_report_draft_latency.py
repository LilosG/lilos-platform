"""Report draft tasks: allow 90 seconds per call (two sequential AI calls ran into 60)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_0001"
down_revision: str | Sequence[str] | None = "20261015_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TASK_KEYS = ("reports.narrative_draft", "reports.topic_grouping")


def _set_latency(milliseconds: int) -> None:
    for key in TASK_KEYS:
        op.execute(
            sa.text(
                "UPDATE ai_task_definitions SET maximum_latency_ms = :latency "
                "WHERE key = :key AND status = 'active'"
            ).bindparams(latency=milliseconds, key=key)
        )


def upgrade() -> None:
    _set_latency(90_000)


def downgrade() -> None:
    _set_latency(60_000)
