# ruff: noqa: E501
"""Create governed Content product and repository publication state."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)

revision = "20260803_0009"
down_revision: str | Sequence[str] | None = "20260803_0008"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (
        ContentOpportunity,
        PublishingTarget,
        ContentItem,
        ContentBrief,
        ContentRevision,
        ContentPublication,
    )
)


def upgrade() -> None:
    for t in TABLES:
        t.create(bind=op.get_bind(), checkfirst=False)
    op.execute(
        """CREATE FUNCTION prevent_content_revision_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.status IN ('approved','published','superseded') THEN RAISE EXCEPTION 'approved content revision is immutable' USING ERRCODE='23514'; END IF; RETURN NEW; END; $$"""
    )
    op.execute(
        "CREATE TRIGGER content_revisions_approved_immutable BEFORE UPDATE OR DELETE ON content_revisions FOR EACH ROW EXECUTE FUNCTION prevent_content_revision_change()"
    )


def downgrade() -> None:
    for t in reversed(TABLES):
        t.drop(bind=op.get_bind(), checkfirst=False)
    op.execute("DROP FUNCTION IF EXISTS prevent_content_revision_change()")
