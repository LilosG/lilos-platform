"""Tenant-scoped Business Profile performance: daily metrics, monthly search keywords, sync runs."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceMetric,
    GBPPerformanceSyncMode,
    GBPPerformanceSyncStatus,
    enum_check,
)


def _gbp_location_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["organization_id", "gbp_location_id"],
        ["gbp_locations.organization_id", "gbp_locations.id"],
        ondelete="RESTRICT",
    )


class GBPPerformanceSyncRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One scheduled or manual pass over one GBP location, and what it wrote."""

    __tablename__ = "gbp_performance_sync_runs"
    __table_args__ = (
        _gbp_location_fk(),
        UniqueConstraint("organization_id", "id", name="uq_gbp_performance_sync_runs_org_id"),
        CheckConstraint(enum_check("status", GBPPerformanceSyncStatus), name="status"),
        CheckConstraint(enum_check("mode", GBPPerformanceSyncMode), name="mode"),
        CheckConstraint("window_start <= window_end", name="window_order"),
        Index(
            "ix_gbp_performance_sync_runs_location_started",
            "organization_id",
            "gbp_location_id",
            "started_at",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    metric_rows_written: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    keyword_rows_written: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failure_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GBPPerformanceDailyMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One metric value for one GBP location on one day, as Google last reported it."""

    __tablename__ = "gbp_performance_daily_metrics"
    __table_args__ = (
        _gbp_location_fk(),
        ForeignKeyConstraint(
            ["organization_id", "sync_run_id"],
            ["gbp_performance_sync_runs.organization_id", "gbp_performance_sync_runs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "gbp_location_id",
            "metric",
            "metric_date",
            name="uq_gbp_performance_daily_metric",
        ),
        CheckConstraint(enum_check("metric", GBPPerformanceMetric), name="metric"),
        CheckConstraint("value >= 0", name="value_non_negative"),
        Index(
            "ix_gbp_performance_daily_metrics_location_date",
            "organization_id",
            "gbp_location_id",
            "metric_date",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    metric: Mapped[str] = mapped_column(String(48), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class GBPPerformanceKeywordImpression(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Profile impressions attributed to one search term in one month.

    Google withholds small counts: it reports "fewer than N" instead of the number. That is
    stored as ``threshold`` (the N) with ``value`` null, so it is never mistaken for zero.
    Exactly one of the two is set.
    """

    __tablename__ = "gbp_performance_keyword_impressions"
    __table_args__ = (
        _gbp_location_fk(),
        ForeignKeyConstraint(
            ["organization_id", "sync_run_id"],
            ["gbp_performance_sync_runs.organization_id", "gbp_performance_sync_runs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "gbp_location_id",
            "month",
            "keyword",
            name="uq_gbp_performance_keyword_impression",
        ),
        CheckConstraint(
            "(value IS NOT NULL) <> (threshold IS NOT NULL)", name="value_xor_threshold"
        ),
        CheckConstraint("value IS NULL OR value >= 0", name="value_non_negative"),
        CheckConstraint("threshold IS NULL OR threshold > 0", name="threshold_positive"),
        CheckConstraint("month = date_trunc('month', month)::date", name="month_is_first_day"),
        Index(
            "ix_gbp_performance_keyword_impressions_location_month",
            "organization_id",
            "gbp_location_id",
            "month",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    value: Mapped[int | None] = mapped_column(Integer)
    threshold: Mapped[int | None] = mapped_column(Integer)
    sync_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
