# ruff: noqa: E501
"""Create evidence-driven SEO product records."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.products.seo.models import (
    SEOCrawlRun,
    SEOImplementationTask,
    SEOOpportunity,
    SEOOutcome,
    SEOPage,
    SEORecommendationRevision,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)

revision = "20260803_0010"
down_revision: str | Sequence[str] | None = "20260803_0009"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (
        SEOWebsite,
        SEOSearchProperty,
        SEOPage,
        SEOCrawlRun,
        SEOSearchObservation,
        SEOOpportunity,
        SEORecommendationRevision,
        SEOImplementationTask,
        SEOOutcome,
    )
)


def upgrade() -> None:
    for table in TABLES:
        table.create(bind=op.get_bind(), checkfirst=False)
    op.execute(
        "CREATE FUNCTION prevent_seo_recommendation_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.status IN ('approved','implemented','rejected') THEN RAISE EXCEPTION 'governed SEO recommendation is immutable' USING ERRCODE='23514'; END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER seo_recommendations_approved_immutable BEFORE UPDATE OR DELETE ON seo_recommendation_revisions FOR EACH ROW EXECUTE FUNCTION prevent_seo_recommendation_change()"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        table.drop(bind=op.get_bind(), checkfirst=False)
    op.execute("DROP FUNCTION IF EXISTS prevent_seo_recommendation_change()")
