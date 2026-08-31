"""Typed immutable contracts for Phase 4 services and APIs."""

from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.api.app.administration.enums import (
    ChecklistSeverity,
    ConfigurationScope,
    ControlState,
    EntitlementStatus,
    FactAuthority,
    OffboardingStatus,
    PolicyCategory,
)
from apps.api.app.administration.validation import (
    validate_governed_document,
    validate_typed_value,
)
from apps.api.app.schemas import ResponseMeta

Key = Annotated[
    str, Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9_]*(?:[.-][a-z0-9_]+)*$")
]
Reason = Annotated[str, Field(min_length=1, max_length=1000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ServiceCreate(Contract):
    key: Annotated[
        str, Field(min_length=3, max_length=63, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    ]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(min_length=1, max_length=1000)] | None = None


class ServiceUpdate(Contract):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    expected_version: int = Field(ge=1)


class ExpectedVersion(Contract):
    expected_version: int = Field(ge=1)


class ServiceAssignmentCreate(Contract):
    service_id: UUID
    scope_type: Literal["organization", "location"]
    location_id: UUID | None = None

    @model_validator(mode="after")
    def scope_consistent(self) -> "ServiceAssignmentCreate":
        if (self.scope_type == "organization") != (self.location_id is None):
            raise ValueError("scope and location_id are inconsistent")
        return self


class BusinessFactPropose(Contract):
    fact_identity: UUID | None = None
    location_id: UUID | None = None
    fact_key: Key
    value_type: Literal["string", "number", "boolean", "object", "string_list"]
    value: Any
    source: Annotated[str, Field(min_length=1, max_length=200)]
    authority: FactAuthority
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    review_at: datetime | None = None
    change_reason: Reason

    @model_validator(mode="after")
    def valid_value(self) -> "BusinessFactPropose":
        validate_typed_value(self.value_type, self.value)
        if (
            self.effective_from
            and self.effective_until
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effective_until must follow effective_from")
        return self


class BusinessFactDecision(Contract):
    decision: Literal["approve", "reject"]


class EntitlementCreate(Contract):
    product_key: Key
    source: Annotated[str, Field(min_length=1, max_length=64)]
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    location_ids: tuple[UUID, ...] = ()
    effective_from: datetime | None = None
    effective_until: datetime | None = None


class EntitlementTransition(Contract):
    target_status: EntitlementStatus
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    expected_version: int = Field(ge=1)


class ConfigurationCreate(Contract):
    configuration_identity: UUID | None = None
    definition_key: Key
    scope_type: ConfigurationScope
    location_id: UUID | None = None
    product_key: Key | None = None
    document: Any
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    change_reason: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator("document")
    @classmethod
    def bounded_document(cls, value: Any) -> Any:
        return validate_governed_document(value)


class RevisionDecision(Contract):
    decision: Literal["approve", "reject"]


class PolicyCreate(Contract):
    policy_identity: UUID | None = None
    policy_key: Key
    category: PolicyCategory
    schema_version: int = Field(ge=1)
    scope_type: ConfigurationScope
    location_id: UUID | None = None
    product_key: Key | None = None
    document: dict[str, Any]
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    change_reason: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator("document")
    @classmethod
    def governed_policy(cls, value: dict[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], validate_governed_document(value, policy=True))


class FeatureFlagCreate(Contract):
    flag_identity: UUID | None = None
    flag_key: Key
    scope_type: Literal["organization", "location"]
    location_id: UUID | None = None
    enabled: bool
    purpose: Annotated[str, Field(min_length=1, max_length=500)]
    risk_class: Literal["low", "medium", "high", "critical"]
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    review_at: datetime


class RuntimeControlCreate(Contract):
    control_identity: UUID | None = None
    capability: Key
    scope_type: ConfigurationScope
    location_id: UUID | None = None
    product_key: Key | None = None
    control_state: ControlState
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    effective_from: datetime | None = None
    effective_until: datetime | None = None


class ChecklistItemCreate(Contract):
    location_id: UUID | None = None
    product_key: Key | None = None
    item_key: Key
    category: Annotated[str, Field(min_length=1, max_length=64)]
    severity: ChecklistSeverity
    automated: bool = False
    remediation: Reason
    required_permission: Annotated[str, Field(min_length=3, max_length=100)]


class ChecklistComplete(Contract):
    evidence: Annotated[str, Field(min_length=1, max_length=1000)]
    expected_version: int = Field(ge=1)


class OffboardingCreate(Contract):
    reason: Reason
    target_date: datetime | None = None


class OffboardingTransition(Contract):
    target_status: OffboardingStatus
    expected_version: int = Field(ge=1)


class OffboardingStepComplete(Contract):
    evidence: Annotated[str, Field(min_length=1, max_length=1000)]
    expected_version: int = Field(ge=1)


class ResolutionSource(Contract):
    layer: str
    record_id: UUID | None
    version: int
    effective_from: datetime | None


class ConfigurationResolution(Contract):
    definition_key: str
    schema_version: int
    value: Any
    valid: bool
    errors: tuple[str, ...]
    sources: tuple[ResolutionSource, ...]
    resolved_at: datetime


class FactResolution(Contract):
    fact_key: str
    state: Literal["resolved", "missing", "ambiguous"]
    selected_revision_id: UUID | None
    fact_identity: UUID | None
    value: Any | None
    authority: FactAuthority | None
    revision: int | None
    scope: str | None
    conflicts: tuple[UUID, ...]


class EffectiveFact(Contract):
    """A single active governed business fact currently in effect."""

    fact_key: str
    revision_id: UUID
    fact_identity: UUID
    value: Any
    value_type: str
    location_id: UUID | None
    source: str
    authority: FactAuthority
    revision: int
    approved_at: datetime | None


class ControlResolution(Contract):
    capability: str
    allowed: bool
    state: ControlState
    winning_control_id: UUID | None
    winning_scope: str | None
    reason: str | None


class BlockerResolution(Contract):
    """Where a blocker is resolved, and by whom.

    Carried alongside the human sentence so the product can render a blocker as
    an action rather than a sentence the operator has to go hunting behind, and
    so a test can assert that everything shown to an operator is clearable by
    that operator.
    """

    # The onboarding step that clears this, when one does. None means the
    # blocker is resolved by a control that is not itself an onboarding step.
    step_key: str | None
    route: str
    # Stable identifier of the control within that route. The frontend uses it
    # as the scroll/focus target, so it is part of the contract, not a hint.
    control: str
    # The permission that clears it. None means it is deliberately not
    # resolvable by an operator inside the platform — an external connection.
    permission: str | None
    label: str


class ReadinessFinding(Contract):
    code: str
    blocking: bool
    resource_key: str | None = None
    remediation: str
    # Additive with a default so existing consumers and stored payloads keep
    # working; every finding the platform emits today populates it.
    resolution: BlockerResolution | None = None


class ProductReadiness(Contract):
    ready: bool
    readiness_state: Literal["ready", "blocked", "not_entitled"]
    product_key: str
    organization_id: UUID
    selected_location_ids: tuple[UUID, ...]
    entitlement_version: int | None
    configuration_versions: tuple[UUID, ...]
    fact_versions: tuple[UUID, ...]
    policy_versions: tuple[UUID, ...]
    blocking_requirements: tuple[ReadinessFinding, ...]
    warnings: tuple[ReadinessFinding, ...]
    evaluated_at: datetime


class OnboardingResolution(Contract):
    organization_id: UUID
    complete: bool
    blockers: tuple[UUID, ...]
    warnings: tuple[UUID, ...]
    evaluated_at: datetime


class DataResponse(Contract):
    data: Any
    meta: ResponseMeta
