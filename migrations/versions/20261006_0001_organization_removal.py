"""Record permanent client removal: a request, a completion, and a database-enforced delete guard.

An archived organization keeps its data. Removal is the second step: the remove endpoint records
``removal_requested_at``, a worker workflow deletes everything the organization owns, and it
finally stamps ``removed_at``. The ``organizations`` row itself is a tombstone and must stay,
because ``audit_events`` is append-only and its organization foreign keys are ``ON DELETE
RESTRICT``.

Removal has to delete rows that governed-history triggers protect (approved content,
recommendations, post and report revisions, entitlements, governed administration history).
Those triggers refuse every DELETE. Each now lets a DELETE through only when the trigger itself
finds that the row's organization is archived, has a removal requested and is not yet removed
(``lilos_organization_removal_in_progress``). There is no session variable or other switch the
caller can set: the state lives in ``organizations`` and is written only by the platform-
administrator-gated remove endpoint. Rows without an organization (the product and configuration
catalogs) and rows of any other organization stay undeletable. UPDATE protection is untouched.
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0001"
down_revision: str | Sequence[str] | None = "20261005_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Governed-history trigger functions that refuse DELETE. Several of them end in ``RETURN NEW``,
# which in a BEFORE DELETE trigger is NULL and silently skips the delete, so the guard returns
# OLD explicitly.
GOVERNED_FUNCTIONS = (
    "prevent_content_revision_change",
    "prevent_seo_recommendation_change",
    "prevent_gbp_post_revision_change",
    "prevent_report_revision_change",
    "prevent_phase4_governed_delete",
)
HELPER = "lilos_organization_removal_in_progress"
GUARD = (
    f"IF TG_OP = 'DELETE' AND {HELPER}((to_jsonb(OLD) ->> 'organization_id')::uuid) "
    "THEN RETURN OLD; END IF;"
)
CHECK = "ck_organizations_archived_timestamp_matches_status"
BEFORE = (
    "(status = 'archived' AND archived_at IS NOT NULL) OR "
    "(status <> 'archived' AND archived_at IS NULL)"
)
AFTER = (
    f"({BEFORE}) AND (removed_at IS NULL OR status = 'archived') "
    "AND (removal_requested_at IS NULL OR status = 'archived')"
)


def _definition(name: str) -> str:
    definition = op.get_bind().scalar(
        sa.text("SELECT pg_get_functiondef(to_regproc(:name))"), {"name": name}
    )
    if not isinstance(definition, str):
        raise RuntimeError(f"governed trigger function {name} is missing")
    return definition


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("organizations")}
    for name in ("removal_requested_at", "removed_at"):
        if name not in columns:
            op.add_column(
                "organizations", sa.Column(name, sa.DateTime(timezone=True), nullable=True)
            )
    op.drop_constraint(op.f(CHECK), "organizations", type_="check")
    op.create_check_constraint(op.f(CHECK), "organizations", AFTER)

    op.execute(
        f"CREATE OR REPLACE FUNCTION {HELPER}(target uuid) RETURNS boolean "
        "LANGUAGE sql STABLE AS $$ "
        "SELECT EXISTS (SELECT 1 FROM organizations AS o WHERE o.id = target "
        "AND o.status = 'archived' AND o.removal_requested_at IS NOT NULL "
        "AND o.removed_at IS NULL) $$"
    )
    for name in GOVERNED_FUNCTIONS:
        definition = _definition(name)
        if GUARD in definition:
            continue
        patched, count = re.subn(r"\bBEGIN\b", f"BEGIN {GUARD}", definition, count=1)
        if count != 1:
            raise RuntimeError(f"cannot find the body of {name}")
        op.execute(patched)


def downgrade() -> None:
    for name in GOVERNED_FUNCTIONS:
        definition = _definition(name)
        if GUARD in definition:
            op.execute(definition.replace(f"BEGIN {GUARD}", "BEGIN", 1))
    op.execute(f"DROP FUNCTION IF EXISTS {HELPER}(uuid)")
    op.drop_constraint(op.f(CHECK), "organizations", type_="check")
    op.create_check_constraint(op.f(CHECK), "organizations", BEFORE)
    op.drop_column("organizations", "removed_at")
    op.drop_column("organizations", "removal_requested_at")
