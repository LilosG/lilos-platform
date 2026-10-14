"""Reports: each revision's calendar month and approval time, and the date a report was sent."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0001"
down_revision: str | Sequence[str] | None = "20261008_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISIONS = "report_revisions"
DELIVERIES = "report_deliveries"
OLD_UNIQUE = "uq_report_revision"
MONTH_UNIQUE = "uq_report_revision_month"
MONTH_CHECK = "ck_report_revisions_month_is_first_day"
MONTH_INDEX = "ix_report_revisions_org_period_month"


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # An older migration builds these tables from the live models, so a fresh database may
    # already have everything below; only existing databases need it added. Both tables are
    # empty everywhere they exist, so the new NOT NULL columns need no backfill.
    if "period_month" not in _columns(REVISIONS):
        op.add_column(
            REVISIONS,
            sa.Column(
                "period_month", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")
            ),
        )
        op.alter_column(REVISIONS, "period_month", server_default=None)
    if "approved_at" not in _columns(REVISIONS):
        op.add_column(
            REVISIONS, sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
        )
    inspector = sa.inspect(op.get_bind())
    uniques = {item["name"] for item in inspector.get_unique_constraints(REVISIONS)}
    if OLD_UNIQUE in uniques:
        op.drop_constraint(OLD_UNIQUE, REVISIONS, type_="unique")
    if MONTH_UNIQUE not in uniques:
        op.create_unique_constraint(
            MONTH_UNIQUE, REVISIONS, ["report_definition_id", "period_month", "revision"]
        )
    if MONTH_CHECK not in {item["name"] for item in inspector.get_check_constraints(REVISIONS)}:
        op.create_check_constraint(
            op.f(MONTH_CHECK), REVISIONS, "period_month = date_trunc('month', period_month)::date"
        )
    if MONTH_INDEX not in {item["name"] for item in inspector.get_indexes(REVISIONS)}:
        op.create_index(MONTH_INDEX, REVISIONS, ["organization_id", "period_month"])
    delivery_columns = _columns(DELIVERIES)
    if "sent_on" not in delivery_columns:
        op.add_column(
            DELIVERIES,
            sa.Column("sent_on", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        )
        op.alter_column(DELIVERIES, "sent_on", server_default=None)
    if "sent_by_user_id" not in delivery_columns:
        op.add_column(
            DELIVERIES,
            sa.Column(
                "sent_by_user_id",
                sa.Uuid(),
                sa.ForeignKey("user_profiles.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    op.drop_column(DELIVERIES, "sent_by_user_id")
    op.drop_column(DELIVERIES, "sent_on")
    op.drop_index(MONTH_INDEX, table_name=REVISIONS)
    op.drop_constraint(op.f(MONTH_CHECK), REVISIONS, type_="check")
    op.drop_constraint(MONTH_UNIQUE, REVISIONS, type_="unique")
    op.create_unique_constraint(OLD_UNIQUE, REVISIONS, ["report_definition_id", "revision"])
    op.drop_column(REVISIONS, "approved_at")
    op.drop_column(REVISIONS, "period_month")
