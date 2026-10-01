"""One pending recommendation revision per opportunity; superseded revisions are terminal.

Creating a new revision used to leave the older one awaiting approval, so an opportunity
could show two live proposals (Coco Maya's 9f7d2c05-... had two) and a human could approve
the stale one. A newer revision now supersedes every older non-terminal one in the same
transaction, and this migration makes the rule structural.

1. The trigger that freezes decided recommendations allows the status-only move
   `awaiting_approval`/`approved` -> `superseded` (as it already does for `withdrawn`);
   `superseded` is terminal.
2. Existing duplicates are repaired: for each opportunity with several `awaiting_approval`
   revisions, every one but the newest (highest revision_number) becomes `superseded`. This
   runs as data repair inside the migration, so unlike runtime supersession it records no
   audit event; the revision rows themselves are kept.
3. A partial unique index allows at most one `awaiting_approval` revision per opportunity.

Revision ID: 20260930_0003
Revises: 20260930_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260930_0003"
down_revision: str | Sequence[str] | None = "20260930_0002"
branch_labels = depends_on = None

TABLE = "seo_recommendation_revisions"
INDEX = "uq_seo_one_pending_revision"
_TAIL = "RAISE EXCEPTION 'governed SEO recommendation is immutable' USING ERRCODE='23514'"


def _function(ended: str, frozen: str) -> str:
    return (
        "CREATE OR REPLACE FUNCTION prevent_seo_recommendation_change() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        f"IF TG_OP = 'UPDATE' AND NEW.status IN ({ended}) "
        "AND OLD.status IN ('awaiting_approval','approved') "
        "AND (to_jsonb(NEW) - 'status') = (to_jsonb(OLD) - 'status') THEN RETURN NEW; END IF; "
        f"IF OLD.status IN ({frozen}) THEN {_TAIL}; END IF; RETURN NEW; END; $$"
    )


def upgrade() -> None:
    op.execute(
        _function(
            "'withdrawn','superseded'",
            "'approved','implemented','rejected','withdrawn','superseded'",
        )
    )
    op.execute(
        f"UPDATE {TABLE} AS older SET status = 'superseded' "
        "WHERE older.status = 'awaiting_approval' AND EXISTS ("
        f"SELECT 1 FROM {TABLE} AS newer "
        "WHERE newer.opportunity_id = older.opportunity_id "
        "AND newer.status = 'awaiting_approval' "
        "AND newer.revision_number > older.revision_number)"
    )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(TABLE)}
    if INDEX not in indexes:
        op.create_index(
            INDEX,
            TABLE,
            ["opportunity_id"],
            unique=True,
            postgresql_where=sa.text("status = 'awaiting_approval'"),
        )


def downgrade() -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(TABLE)}
    if INDEX in indexes:
        op.drop_index(INDEX, table_name=TABLE)
    # `superseded` rows are kept; the earlier trigger simply treats them as unknown.
    op.execute(_function("'withdrawn'", "'approved','implemented','rejected','withdrawn'"))
