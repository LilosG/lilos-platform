"""SQLAlchemy model for append-only audit events."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.database.base import Base


def _enum_values(enum_class: type[AuditActorType] | type[AuditResult]) -> list[str]:
    return [item.value for item in enum_class]


class AuditEvent(Base):
    """Durable evidence for a significant platform action."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("length(btrim(event_type)) > 0", name="event_type_not_blank"),
        CheckConstraint("length(btrim(action)) > 0", name="action_not_blank"),
        CheckConstraint("length(btrim(summary)) > 0", name="summary_not_blank"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_is_object"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    result: Mapped[AuditResult] = mapped_column(
        Enum(
            AuditResult,
            name="audit_result",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_enum_values,
            length=32,
        ),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    actor_type: Mapped[AuditActorType] = mapped_column(
        Enum(
            AuditActorType,
            name="audit_actor_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_enum_values,
            length=32,
        ),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    actor_display_reference: Mapped[str | None] = mapped_column(String(200))
    organization_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_audit_events_organization_id_organizations",
            ondelete="RESTRICT",
        ),
    )
    location_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "locations.id",
            name="fk_audit_events_location_id_locations",
            ondelete="RESTRICT",
        ),
    )
    product_key: Mapped[str | None] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    workflow_execution_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    source_ip: Mapped[str | None] = mapped_column(INET)
    user_agent_summary: Mapped[str | None] = mapped_column(String(256))
    reason_code: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    approval_reference_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    previous_audit_event_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "audit_events.id",
            name="fk_audit_events_previous_audit_event_id_audit_events",
            ondelete="RESTRICT",
        ),
    )


Index(
    "ix_audit_events_occurred_at_id",
    AuditEvent.occurred_at.desc(),
    AuditEvent.id.desc(),
)
Index(
    "ix_audit_events_organization_occurred_at_id",
    AuditEvent.organization_id,
    AuditEvent.occurred_at.desc(),
    AuditEvent.id.desc(),
)
Index("ix_audit_events_correlation_id", AuditEvent.correlation_id)
Index(
    "ix_audit_events_location_occurred_at_id",
    AuditEvent.location_id,
    AuditEvent.occurred_at.desc(),
    AuditEvent.id.desc(),
)
Index(
    "ix_audit_events_resource_occurred_at_id",
    AuditEvent.resource_type,
    AuditEvent.resource_id,
    AuditEvent.occurred_at.desc(),
    AuditEvent.id.desc(),
)
Index("ix_audit_events_previous_audit_event_id", AuditEvent.previous_audit_event_id)
