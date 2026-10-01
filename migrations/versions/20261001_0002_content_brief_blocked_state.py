"""Content briefs can be blocked with a typed reason instead of sitting `ready` without sources.

A brief with empty `source_evidence_references` was written as `ready`, which guaranteed
the draft tool's "draft sources must be non-empty references from the ready brief" denial.
Briefs now regenerate their sources from the opportunity's governed evidence, or are
`blocked` with `blocked_reason_code`. The status check also admits the terminal states
(`retired`, `superseded`, `rejected`, `failed`) that retirement and growth artifacts use.

Existing empty-source `ready` briefs are left for `scripts.retire_stale_growth_work`, which
regenerates or blocks them through the service so each change is audited.

Revision ID: 20261001_0002
Revises: 20261001_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261001_0002"
down_revision: str | Sequence[str] | None = "20261001_0001"
branch_labels = depends_on = None

TABLE = "content_briefs"
CONSTRAINT = "ck_content_briefs_status"
STATUSES = "status IN ('ready','blocked','retired','superseded','rejected','failed')"


def _has_constraint(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == name for c in inspector.get_check_constraints(TABLE))


def upgrade() -> None:
    # 20260803_0009 builds content tables from the live models; stay idempotent.
    op.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS blocked_reason_code varchar(64)")
    if not _has_constraint(CONSTRAINT):
        # The metadata naming convention prefixes `ck_<table>_`, so pass the short name.
        op.create_check_constraint("status", TABLE, sa.text(STATUSES))


def downgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS blocked_reason_code")
