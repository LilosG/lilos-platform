# ruff: noqa: E501
"""Create definition-driven insights and immutable reporting."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.insights.models import (
    InsightAnnotation,
    InsightGoal,
    InsightRecord,
    InsightSource,
    MetricDefinition,
    MetricObservation,
    ReportDefinition,
    ReportDelivery,
    ReportRevision,
)

revision = "20260803_0012"
down_revision: str | Sequence[str] | None = "20260803_0011"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (
        InsightSource,
        MetricDefinition,
        MetricObservation,
        InsightGoal,
        InsightAnnotation,
        ReportDefinition,
        ReportRevision,
        ReportDelivery,
        InsightRecord,
    )
)


def upgrade() -> None:
    for table in TABLES:
        table.create(bind=op.get_bind(), checkfirst=False)
    op.execute(
        "CREATE FUNCTION prevent_report_revision_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.status IN ('approved','published','delivered') THEN RAISE EXCEPTION 'published report revision is immutable' USING ERRCODE='23514'; END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER report_revisions_published_immutable BEFORE UPDATE OR DELETE ON report_revisions FOR EACH ROW EXECUTE FUNCTION prevent_report_revision_change()"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        table.drop(bind=op.get_bind(), checkfirst=False)
    op.execute("DROP FUNCTION IF EXISTS prevent_report_revision_change()")
