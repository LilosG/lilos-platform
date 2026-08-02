"""Typed creation contract for immutable audit events."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, field_validator

from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue, normalize_audit_metadata
from apps.api.app.database.base import utc_now

NamespacedKey = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$"),
]
ShortReference = Annotated[str, Field(min_length=1, max_length=200)]
ReasonCode = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$"),
]
CorrelationId = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"),
]


class AuditEventCreate(BaseModel):
    """Explicit validated input used to append one audit event."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    event_type: NamespacedKey
    action: NamespacedKey
    result: AuditResult
    occurred_at: datetime = Field(default_factory=utc_now)
    actor_type: AuditActorType
    actor_id: UUID | None = None
    actor_display_reference: ShortReference | None = None
    organization_id: UUID | None = None
    location_id: UUID | None = None
    product_key: (
        Annotated[
            str,
            Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
        ]
        | None
    ) = None
    resource_type: (
        Annotated[
            str,
            Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$"),
        ]
        | None
    ) = None
    resource_id: UUID | None = None
    correlation_id: CorrelationId | None = None
    workflow_execution_id: UUID | None = None
    source_ip: IPvAnyAddress | None = None
    user_agent_summary: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    reason_code: ReasonCode | None = None
    summary: Annotated[str, Field(min_length=1, max_length=500)]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    error_code: ReasonCode | None = None
    approval_reference_id: UUID | None = None
    previous_audit_event_id: UUID | None = None

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        """Require an aware timestamp and normalize it to UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include timezone information")
        return value.astimezone(UTC)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: Any) -> dict[str, JsonValue]:
        """Validate and defensively copy structured metadata."""
        return normalize_audit_metadata(value)
