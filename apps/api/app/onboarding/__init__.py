"""Client-onboarding orchestration: a read model composing existing services.

Introduces no new authoritative business logic. Every fact reported here is
resolved live from the owning domain service (organizations, locations,
domains, profiles, administration's services/business-facts/entitlements/
policies/onboarding-checklist, access-control memberships/invitations) at
request time, so it can never drift from what those services would report
directly.

OnboardingResponsibilityMode controls who may perform each step over the
SAME underlying engine; it never creates a parallel architecture.
"""

from apps.api.app.onboarding.contracts import (
    OnboardingClientState,
    OnboardingModeControl,
    OnboardingModeSetRequest,
    OnboardingProductStatus,
    OnboardingResponsibilityMode,
    OnboardingState,
    OnboardingStateResponse,
    OnboardingStep,
    OnboardingStepAssignment,
    OnboardingStepState,
    StepAssignmentRequest,
)
from apps.api.app.onboarding.models import OnboardingStepAssignmentRecord
from apps.api.app.onboarding.service import OnboardingOrchestrationService

__all__ = [
    "OnboardingClientState",
    "OnboardingModeControl",
    "OnboardingModeSetRequest",
    "OnboardingOrchestrationService",
    "OnboardingProductStatus",
    "OnboardingResponsibilityMode",
    "OnboardingState",
    "OnboardingStateResponse",
    "OnboardingStep",
    "OnboardingStepAssignment",
    "OnboardingStepAssignmentRecord",
    "OnboardingStepState",
    "StepAssignmentRequest",
]
