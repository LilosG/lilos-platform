"""Allow an SEO recommendation to be withdrawn, and nothing else to change once decided.

Approved recommendations are frozen by a trigger so what a human approved can never be
edited. Two kinds of recommendation can nevertheless become impossible to act on: one
whose opportunity was archived, and an approval that predates page attribution and so
can never execute. Both must leave the queue. This teaches the trigger exactly one
exception -- `awaiting_approval` or `approved` -> `withdrawn`, with every other column
unchanged -- and makes `withdrawn` terminal. Deletes stay blocked, and any other edit to
a decided recommendation is still refused.

Revision ID: 20260930_0002
Revises: 20260930_0001
"""

from collections.abc import Sequence

from alembic import op

revision = "20260930_0002"
down_revision: str | Sequence[str] | None = "20260930_0001"
branch_labels = depends_on = None

_TAIL = "RAISE EXCEPTION 'governed SEO recommendation is immutable' USING ERRCODE='23514'"


def upgrade() -> None:
    op.execute(
        "CREATE OR REPLACE FUNCTION prevent_seo_recommendation_change() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP = 'UPDATE' AND NEW.status = 'withdrawn' "
        "AND OLD.status IN ('awaiting_approval','approved') "
        "AND (to_jsonb(NEW) - 'status') = (to_jsonb(OLD) - 'status') THEN RETURN NEW; END IF; "
        "IF OLD.status IN ('approved','implemented','rejected','withdrawn') THEN "
        f"{_TAIL}; END IF; RETURN NEW; END; $$"
    )


def downgrade() -> None:
    op.execute(
        "CREATE OR REPLACE FUNCTION prevent_seo_recommendation_change() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "IF OLD.status IN ('approved','implemented','rejected') THEN "
        f"{_TAIL}; END IF; RETURN NEW; END; $$"
    )
