"""Reports: a period of 1 to 12 months and the comparison each revision was built against."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0001"
down_revision: str | Sequence[str] | None = "20261014_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISIONS = "report_revisions"
UNIQUE = "uq_report_revision_month"
INDEX = "ix_report_revisions_org_period_month"
IMMUTABLE_TRIGGER = "report_revisions_published_immutable"
CHECKS = {
    "ck_report_revisions_end_month_is_first_day": (
        "period_end_month = date_trunc('month', period_end_month)::date"
    ),
    "ck_report_revisions_period_not_reversed": "period_end_month >= period_month",
    "ck_report_revisions_period_within_12_months": (
        "(extract(year from period_end_month) * 12 + extract(month from period_end_month))"
        " - (extract(year from period_month) * 12 + extract(month from period_month)) < 12"
    ),
    "ck_report_revisions_comparison_key_valid": (
        "comparison_key ~ '^(previous|year_ago|baseline:[0-9]{4}-[0-9]{2}:[0-9]{4}-[0-9]{2})$'"
    ),
}
# The snapshot schema this migration's code writes (SNAPSHOT_SCHEMA_VERSION). A snapshot of an
# older schema has no period, comparison, headlines or monthly series and cannot be read.
SNAPSHOT_SCHEMA_VERSION = 2
OLD_SCHEMA = "COALESCE((metric_snapshot->'snapshot'->>'schema_version')::int, 0) < :version"


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(REVISIONS)}


def _retire_old_snapshots() -> None:
    """Drafts of an older schema are regenerable and deleted; approved ones are never touched."""
    bind = op.get_bind()
    approved = bind.execute(
        sa.text(f"SELECT count(*) FROM {REVISIONS} WHERE status <> 'draft' AND {OLD_SCHEMA}"),
        {"version": SNAPSHOT_SCHEMA_VERSION},
    ).scalar_one()
    if approved:
        raise RuntimeError(
            f"{approved} approved report revision(s) hold a snapshot of an older schema. "
            "They are immutable and cannot be converted here; handle them before migrating."
        )
    # The immutability trigger answers every DELETE with NULL, which silently skips the row. Only
    # drafts of an older schema are deleted, with the trigger lifted for this one statement.
    bind.execute(sa.text(f"ALTER TABLE {REVISIONS} DISABLE TRIGGER {IMMUTABLE_TRIGGER}"))
    bind.execute(
        sa.text(f"DELETE FROM {REVISIONS} WHERE status = 'draft' AND {OLD_SCHEMA}"),
        {"version": SNAPSHOT_SCHEMA_VERSION},
    )
    bind.execute(sa.text(f"ALTER TABLE {REVISIONS} ENABLE TRIGGER {IMMUTABLE_TRIGGER}"))


def upgrade() -> None:
    # An older migration builds this table from the live models, so a fresh database may
    # already have everything below; only existing databases need it added.
    _retire_old_snapshots()
    columns = _columns()
    if "period_end_month" not in columns:
        op.add_column(REVISIONS, sa.Column("period_end_month", sa.Date(), nullable=True))
        op.execute(f"UPDATE {REVISIONS} SET period_end_month = period_month")
        op.alter_column(REVISIONS, "period_end_month", nullable=False)
    if "comparison_key" not in columns:
        op.add_column(
            REVISIONS,
            sa.Column(
                "comparison_key",
                sa.String(40),
                nullable=False,
                server_default="previous",
            ),
        )
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_check_constraints(REVISIONS)}
    for name, expression in CHECKS.items():
        if name not in existing:
            op.create_check_constraint(op.f(name), REVISIONS, expression)
    unique = next(
        (item for item in inspector.get_unique_constraints(REVISIONS) if item["name"] == UNIQUE),
        None,
    )
    if unique is None or "comparison_key" not in unique["column_names"]:
        if unique is not None:
            op.drop_constraint(UNIQUE, REVISIONS, type_="unique")
        op.create_unique_constraint(
            UNIQUE,
            REVISIONS,
            [
                "report_definition_id",
                "period_month",
                "period_end_month",
                "comparison_key",
                "revision",
            ],
        )
    index = next((item for item in inspector.get_indexes(REVISIONS) if item["name"] == INDEX), None)
    if index is None or "period_end_month" not in index["column_names"]:
        if index is not None:
            op.drop_index(INDEX, table_name=REVISIONS)
        op.create_index(INDEX, REVISIONS, ["organization_id", "period_month", "period_end_month"])


def downgrade() -> None:
    """Back to one month per report. Reports the single-month layout cannot hold are removed.

    A multi-month report, or one against another comparison, has no place in the old layout
    (revisions were numbered per month). Those revisions and their delivery records are deleted;
    the immutability trigger is lifted for that statement only.
    """
    bind = op.get_bind()
    unrepresentable = (
        f"SELECT id FROM {REVISIONS} "
        "WHERE period_end_month <> period_month OR comparison_key <> 'previous'"
    )
    bind.execute(
        sa.text(f"DELETE FROM report_deliveries WHERE report_revision_id IN ({unrepresentable})")
    )
    bind.execute(sa.text(f"ALTER TABLE {REVISIONS} DISABLE TRIGGER {IMMUTABLE_TRIGGER}"))
    bind.execute(sa.text(f"DELETE FROM {REVISIONS} WHERE id IN ({unrepresentable})"))
    bind.execute(sa.text(f"ALTER TABLE {REVISIONS} ENABLE TRIGGER {IMMUTABLE_TRIGGER}"))
    op.drop_index(INDEX, table_name=REVISIONS)
    op.create_index(INDEX, REVISIONS, ["organization_id", "period_month"])
    op.drop_constraint(UNIQUE, REVISIONS, type_="unique")
    op.create_unique_constraint(
        UNIQUE, REVISIONS, ["report_definition_id", "period_month", "revision"]
    )
    for name in CHECKS:
        op.drop_constraint(op.f(name), REVISIONS, type_="check")
    op.drop_column(REVISIONS, "comparison_key")
    op.drop_column(REVISIONS, "period_end_month")
