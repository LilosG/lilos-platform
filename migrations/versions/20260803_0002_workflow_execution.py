# ruff: noqa: E501
"""Create durable workflow and job foundation."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.execution.models import (
    IdempotencyRecord,
    Job,
    JobAttempt,
    Schedule,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
    WorkflowVersion,
)

revision: str = "20260803_0002"
down_revision: str | Sequence[str] | None = "20260803_0001"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, model.__table__)
    for model in (
        WorkflowDefinition,
        WorkflowVersion,
        WorkflowRun,
        WorkflowStep,
        Job,
        JobAttempt,
        Schedule,
        IdempotencyRecord,
    )
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=False)
