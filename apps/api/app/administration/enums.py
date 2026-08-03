"""Controlled Phase 4 administration values."""

from enum import StrEnum


class ServiceStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class FactStatus(StrEnum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    REJECTED = "rejected"


class FactAuthority(StrEnum):
    CLIENT_APPROVED = "client_approved"
    OPERATOR_VERIFIED = "operator_verified"
    PROVIDER_OBSERVED = "provider_observed"
    IMPORTED = "imported"
    SYSTEM_DERIVED = "system_derived"
    INDUSTRY_DEFAULT = "industry_default"
    AI_SUGGESTED = "ai_suggested"


class ProductStatus(StrEnum):
    REGISTERED = "registered"


class EntitlementStatus(StrEnum):
    NOT_ENABLED = "not_enabled"
    SETUP_REQUIRED = "setup_required"
    CONFIGURATION_REQUIRED = "configuration_required"
    CONNECTION_REQUIRED = "connection_required"
    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class RevisionStatus(StrEnum):
    DRAFT = "draft"
    VALIDATION_FAILED = "validation_failed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class ConfigurationScope(StrEnum):
    ORGANIZATION = "organization"
    LOCATION = "location"
    PRODUCT = "product"


class MergeStrategy(StrEnum):
    REPLACE = "replace"
    OBJECT_MERGE = "object_merge"
    APPEND_UNIQUE = "append_unique"


class PolicyCategory(StrEnum):
    GENERAL = "general"
    APPROVAL = "approval"
    NOTIFICATION = "notification"


class ControlState(StrEnum):
    ALLOWED = "allowed"
    DEGRADED = "degraded"
    PAUSED = "paused"
    DISABLED = "disabled"


class ChecklistStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class ChecklistSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"


class OffboardingStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
