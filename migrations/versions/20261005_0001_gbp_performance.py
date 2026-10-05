"""Business Profile performance: daily metrics, monthly search keywords and sync runs.

Revision ID: 20261005_0001
Revises: 20261002_0002
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceMetric,
    GBPPerformanceSyncMode,
    GBPPerformanceSyncStatus,
    enum_check,
)

revision: str = "20261005_0001"
down_revision: str | Sequence[str] | None = "20261002_0002"
branch_labels = depends_on = None

_LOCATION_FK = (
    ["organization_id", "gbp_location_id"],
    ["gbp_locations.organization_id", "gbp_locations.id"],
)
_RUN_FK = (
    ["organization_id", "sync_run_id"],
    ["gbp_performance_sync_runs.organization_id", "gbp_performance_sync_runs.id"],
)


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "gbp_performance_sync_runs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("gbp_location_id", uuid, nullable=False),
        sa.Column("workflow_run_id", uuid),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("metric_rows_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("keyword_rows_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_code", sa.String(64)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(*_LOCATION_FK, ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "id", name="uq_gbp_performance_sync_runs_org_id"),
        sa.CheckConstraint(
            enum_check("status", GBPPerformanceSyncStatus),
            name=op.f("ck_gbp_performance_sync_runs_status"),
        ),
        sa.CheckConstraint(
            enum_check("mode", GBPPerformanceSyncMode),
            name=op.f("ck_gbp_performance_sync_runs_mode"),
        ),
        sa.CheckConstraint(
            "window_start <= window_end", name=op.f("ck_gbp_performance_sync_runs_window_order")
        ),
    )
    op.create_index(
        "ix_gbp_performance_sync_runs_location_started",
        "gbp_performance_sync_runs",
        ["organization_id", "gbp_location_id", "started_at"],
    )

    op.create_table(
        "gbp_performance_daily_metrics",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("gbp_location_id", uuid, nullable=False),
        sa.Column("metric", sa.String(48), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", uuid, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(*_LOCATION_FK, ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(*_RUN_FK, ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "organization_id",
            "gbp_location_id",
            "metric",
            "metric_date",
            name="uq_gbp_performance_daily_metric",
        ),
        sa.CheckConstraint(
            enum_check("metric", GBPPerformanceMetric),
            name=op.f("ck_gbp_performance_daily_metrics_metric"),
        ),
        sa.CheckConstraint(
            "value >= 0", name=op.f("ck_gbp_performance_daily_metrics_value_non_negative")
        ),
    )
    op.create_index(
        "ix_gbp_performance_daily_metrics_location_date",
        "gbp_performance_daily_metrics",
        ["organization_id", "gbp_location_id", "metric_date"],
    )

    op.create_table(
        "gbp_performance_keyword_impressions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("gbp_location_id", uuid, nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("value", sa.Integer()),
        sa.Column("threshold", sa.Integer()),
        sa.Column("sync_run_id", uuid, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(*_LOCATION_FK, ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(*_RUN_FK, ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "organization_id",
            "gbp_location_id",
            "month",
            "keyword",
            name="uq_gbp_performance_keyword_impression",
        ),
        sa.CheckConstraint(
            "(value IS NOT NULL) <> (threshold IS NOT NULL)",
            name=op.f("ck_gbp_performance_keyword_impressions_value_xor_threshold"),
        ),
        sa.CheckConstraint(
            "value IS NULL OR value >= 0",
            name=op.f("ck_gbp_performance_keyword_impressions_value_non_negative"),
        ),
        sa.CheckConstraint(
            "threshold IS NULL OR threshold > 0",
            name=op.f("ck_gbp_performance_keyword_impressions_threshold_positive"),
        ),
        sa.CheckConstraint(
            "month = date_trunc('month', month)::date",
            name=op.f("ck_gbp_performance_keyword_impressions_month_is_first_day"),
        ),
    )
    op.create_index(
        "ix_gbp_performance_keyword_impressions_location_month",
        "gbp_performance_keyword_impressions",
        ["organization_id", "gbp_location_id", "month"],
    )


def downgrade() -> None:
    op.drop_table("gbp_performance_keyword_impressions")
    op.drop_table("gbp_performance_daily_metrics")
    op.drop_table("gbp_performance_sync_runs")
