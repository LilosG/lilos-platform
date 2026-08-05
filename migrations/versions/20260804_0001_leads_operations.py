# ruff: noqa: E501
"""Add lead notes and tasks with tenant RLS.

The `leads` table itself is created by migration `20260803_0008` directly from
the live `Lead` ORM model (this codebase's migrations create tables from
current model state rather than frozen snapshots), so the `converted_value_cents`
and `loss_reason` columns added to that model are already part of that
migration's `CREATE TABLE` and require no separate `ALTER TABLE` here.
"""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.products.leads.models import LeadNote, LeadTask

revision = "20260804_0001"
down_revision: str | Sequence[str] | None = "20260803_0013"
branch_labels = depends_on = None
TABLES = tuple(cast(Table, m.__table__) for m in (LeadNote, LeadTask))


def upgrade() -> None:
    for table in TABLES:
        table.create(bind=op.get_bind(), checkfirst=False)
    for table in ("lead_notes", "lead_tasks"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} USING (organization_id = NULLIF(current_setting('lilos.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('lilos.organization_id', true), '')::uuid)"
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        table.drop(bind=op.get_bind(), checkfirst=False)
