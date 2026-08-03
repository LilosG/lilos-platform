# ruff: noqa: E501
"""Create remaining capability-governed GBP operations."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.products.gbp.operations_models import (
    GBPCapabilitySnapshot,
    GBPCategory,
    GBPChangeSet,
    GBPMedia,
    GBPPostPublication,
    GBPPostRevision,
    GBPSpecialHours,
    GBPSuspensionCase,
)

revision = "20260803_0011"
down_revision: str | Sequence[str] | None = "20260803_0010"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (
        GBPCapabilitySnapshot,
        GBPCategory,
        GBPChangeSet,
        GBPSpecialHours,
        GBPMedia,
        GBPPostRevision,
        GBPPostPublication,
        GBPSuspensionCase,
    )
)


def upgrade() -> None:
    for table in TABLES:
        table.create(bind=op.get_bind(), checkfirst=False)
    op.execute(
        "CREATE FUNCTION prevent_gbp_post_revision_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.status IN ('approved','published','rejected') THEN RAISE EXCEPTION 'governed GBP post revision is immutable' USING ERRCODE='23514'; END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER gbp_post_revisions_approved_immutable BEFORE UPDATE OR DELETE ON gbp_post_revisions FOR EACH ROW EXECUTE FUNCTION prevent_gbp_post_revision_change()"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        table.drop(bind=op.get_bind(), checkfirst=False)
    op.execute("DROP FUNCTION IF EXISTS prevent_gbp_post_revision_change()")
