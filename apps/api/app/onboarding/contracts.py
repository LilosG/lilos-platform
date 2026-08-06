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


class OnboardingStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    state: OnboardingStepState
    blocking: bool
    detail: str
    next_action: str | None


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
