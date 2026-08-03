"""Persistent incident, timeline, heartbeat, and SLO records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OperationalIncident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_incidents"
    __table_args__ = (
        UniqueConstraint("environment", "key", name="uq_operational_incidents_environment_key"),
        CheckConstraint("severity IN ('sev1','sev2','sev3','sev4')", name="severity"),
        CheckConstraint(
            "status IN ('detected','investigating','identified','mitigating',"
            "'monitoring','resolved','closed')",
            name="status",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    affected_context: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    owner_reference: Mapped[str | None] = mapped_column(String(200))
    runbook_key: Mapped[str] = mapped_column(String(128), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mitigated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    postmortem_reference: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class IncidentTimelineEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "incident_timeline_entries"
    __table_args__ = (
        UniqueConstraint("incident_id", "sequence", name="uq_incident_timeline_sequence"),
    )
    incident_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("operational_incidents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ServiceHeartbeat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_heartbeats"
    __table_args__ = (
        UniqueConstraint("environment", "service", "instance_key", name="uq_service_heartbeat"),
    )
    environment: Mapped[str] = mapped_column(String(24), nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False)
    instance_key: Mapped[str] = mapped_column(String(128), nullable=False)
    release: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    safe_details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class SLORecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "slo_definitions"
    __table_args__ = (UniqueConstraint("key", "version", name="uq_slo_definition_version"),)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False)
    sli_key: Mapped[str] = mapped_column(String(128), nullable=False)
    target_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    exclusions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    alert_policy_key: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
