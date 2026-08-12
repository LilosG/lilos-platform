"""Typed onboarding read-model contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.app.schemas import ResponseMeta


class OnboardingStepState(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    OPTIONAL_INCOMPLETE = "optional_incomplete"


class OnboardingResponsibilityMode(StrEnum):
    """Controls who may perform each onboarding step.

    These are operating modes over ONE onboarding engine. They must not alter
    the underlying definition of completion/readiness; they only gate who is
    permitted to drive each step.
    """

    MANAGED = "managed"
    CO_MANAGED = "co_managed"
    SELF_SERVICE = "self_service"


class OnboardingStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    state: OnboardingStepState
    blocking: bool
    detail: str
    next_action: str | None


class OnboardingStepAssignment(BaseModel):
    """A co-managed step that has been delegated to either agency or client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_key: str
    assigned_to: str  # "agency" or "client"
    assigned_at: datetime


class OnboardingModeControl(BaseModel):
    """Deterministic responsibility-mode contract for a single step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_key: str
    managed: bool = True  # agency may always perform
    co_managed_agency: bool = True  # agency may perform in co-managed
    co_managed_client: bool = False  # client may perform in co-managed
    self_service_client: bool = False  # client may perform in self-service


class OnboardingProductStatus(BaseModel):
    """Truthful per-product status, kept separate from entitlement existence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_key: str
    product_name: str
    selected: bool
    entitlement_status: str | None
    readiness_state: str | None
    ready: bool
    blocking_findings: tuple[str, ...]
    external_integration_pending: bool
    next_action: str | None


class OnboardingState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    organization_name: str
    organization_status: str
    organization_version: int
    responsibility_mode: OnboardingResponsibilityMode | None = None
    steps: tuple[OnboardingStep, ...]
    products: tuple[OnboardingProductStatus, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    progress_percent: Annotated[int, Field(ge=0, le=100)]
    activation_eligible: bool
    evaluated_at: datetime


class OnboardingStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: OnboardingState
    meta: ResponseMeta


class OnboardingModeSetRequest(BaseModel):
    """Set or update the responsibility mode for an organization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: OnboardingResponsibilityMode
    expected_version: Annotated[int, Field(ge=1)]


class StepAssignmentRequest(BaseModel):
    """Assign a co-managed step to agency or client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_key: str
    assigned_to: str  # "agency" or "client"


class OnboardingClientState(BaseModel):
    """Client-visible onboarding state filtered by responsibility mode and role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    organization_name: str
    responsibility_mode: OnboardingResponsibilityMode | None = None
    visible_steps: tuple[OnboardingStep, ...]
    accessible_product_keys: tuple[str, ...]
    activation_eligible: bool
    progress_percent: Annotated[int, Field(ge=0, le=100)]
    evaluated_at: datetime
