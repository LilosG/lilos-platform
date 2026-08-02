"""Stable audit-event classifications shared by contracts and persistence."""

from enum import StrEnum


class AuditActorType(StrEnum):
    """Identity category responsible for an audited action."""

    USER = "user"
    SERVICE = "service"
    WORKFLOW = "workflow"
    SYSTEM = "system"
    EXTERNAL_PROVIDER = "external_provider"


class AuditResult(StrEnum):
    """Stable outcome category for an audited action."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    CANCELLED = "cancelled"
