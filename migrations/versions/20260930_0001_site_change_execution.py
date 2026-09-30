"""Let the content publication state machine carry governed SEO site changes.

A site change reuses `content_publications` end to end (branch, pull request,
checks, merge, deployment) instead of growing a parallel system, so that table
learns a second kind of subject: an approved SEO recommendation revision rather
than a Content item + revision. Publishing targets gain a separate allow-list of
prefixes a site change may edit (`allowed_path_prefix` stays blog-only), and a
recommendation revision records a typed code when it carries no change set.

Revision ID: 20260930_0001
Revises: 20260929_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260930_0001"
down_revision: str | Sequence[str] | None = "20260929_0004"
branch_labels = depends_on = None

PUBLICATIONS = "content_publications"
TARGETS = "publishing_targets"
REVISIONS = "seo_recommendation_revisions"
KIND_CHECK = "ck_content_publications_publication_kind"
SUBJECT_CHECK = "ck_content_publications_publication_subject"
SUBJECT_FK = "fk_content_publications_seo_recommendation_revision_id_seo_recommendation_revisions"


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {str(check["name"]) for check in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    target_columns = _columns(TARGETS)
    if "allowed_site_change_prefixes" not in target_columns:
        op.add_column(
            TARGETS,
            sa.Column(
                "allowed_site_change_prefixes",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    columns = _columns(PUBLICATIONS)
    if "publication_kind" not in columns:
        op.add_column(
            PUBLICATIONS,
            sa.Column("publication_kind", sa.String(16), nullable=False, server_default="content"),
        )
    if "seo_recommendation_revision_id" not in columns:
        op.add_column(
            PUBLICATIONS,
            sa.Column("seo_recommendation_revision_id", postgresql.UUID(as_uuid=True)),
        )
    if "change_set_fingerprint" not in columns:
        op.add_column(PUBLICATIONS, sa.Column("change_set_fingerprint", sa.String(64)))
    if "verification_status" not in columns:
        op.add_column(PUBLICATIONS, sa.Column("verification_status", sa.String(32)))
    if "verification_evidence" not in columns:
        op.add_column(PUBLICATIONS, sa.Column("verification_evidence", postgresql.JSONB()))

    op.alter_column(PUBLICATIONS, "content_item_id", nullable=True)
    op.alter_column(PUBLICATIONS, "content_revision_id", nullable=True)

    checks = _checks(PUBLICATIONS)
    if KIND_CHECK not in checks:
        op.create_check_constraint(
            "publication_kind", PUBLICATIONS, "publication_kind IN ('content','site_change')"
        )
    if SUBJECT_CHECK not in checks:
        op.create_check_constraint(
            "publication_subject",
            PUBLICATIONS,
            "(publication_kind = 'content' AND content_item_id IS NOT NULL "
            "AND content_revision_id IS NOT NULL AND seo_recommendation_revision_id IS NULL) "
            "OR (publication_kind = 'site_change' AND content_item_id IS NULL "
            "AND content_revision_id IS NULL AND seo_recommendation_revision_id IS NOT NULL)",
        )

    if "change_set_limitation_code" not in _columns(REVISIONS):
        op.add_column(REVISIONS, sa.Column("change_set_limitation_code", sa.String(64)))


def downgrade() -> None:
    if "change_set_limitation_code" in _columns(REVISIONS):
        op.drop_column(REVISIONS, "change_set_limitation_code")

    # Site-change rows have no content subject and cannot survive the old NOT NULL
    # shape; they are provider-lifecycle records, so removing them is the only
    # faithful downgrade.
    columns = _columns(PUBLICATIONS)
    if "publication_kind" in columns:
        op.execute(f"DELETE FROM {PUBLICATIONS} WHERE publication_kind = 'site_change'")
    checks = _checks(PUBLICATIONS)
    if SUBJECT_CHECK in checks:
        op.drop_constraint(op.f(SUBJECT_CHECK), PUBLICATIONS, type_="check")
    if KIND_CHECK in checks:
        op.drop_constraint(op.f(KIND_CHECK), PUBLICATIONS, type_="check")
    op.alter_column(PUBLICATIONS, "content_revision_id", nullable=False)
    op.alter_column(PUBLICATIONS, "content_item_id", nullable=False)
    for name in (
        "verification_evidence",
        "verification_status",
        "change_set_fingerprint",
    ):
        if name in columns:
            op.drop_column(PUBLICATIONS, name)
    if "seo_recommendation_revision_id" in columns:
        op.drop_column(PUBLICATIONS, "seo_recommendation_revision_id")
    if "publication_kind" in columns:
        op.drop_column(PUBLICATIONS, "publication_kind")

    if "allowed_site_change_prefixes" in _columns(TARGETS):
        op.drop_column(TARGETS, "allowed_site_change_prefixes")
