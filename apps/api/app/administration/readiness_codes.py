"""The closed set of readiness findings, and where each one is resolved.

A blocker used to be a sentence. ``ReadinessFinding`` carried a ``code`` string
and a ``remediation`` sentence, and nothing else — no destination, no owning
permission, no statement of who could clear it. The product could therefore
show an operator a blocker that operator had no way to act on, and no test
could fail for it, because "is this resolvable?" was not a question the types
could express.

This module makes it expressible. ``ReadinessCode`` closes the set of findings
so the resolution registry can be exhaustive by construction: adding a finding
without saying where it is resolved is a type error, not a silent regression.
``RESOLUTIONS`` is that registry, and ``tests/python/onboarding`` asserts the
deadlock-freedom property over it — every blocker reachable during onboarding
must be clearable by the operator being shown it.
"""

from enum import StrEnum

from apps.api.app.administration.contracts import BlockerResolution, ReadinessFinding


class ReadinessCode(StrEnum):
    """Every readiness finding the platform can emit."""

    APPROVAL_POLICY_MISSING = "APPROVAL_POLICY_MISSING"
    BUSINESS_FACT_UNRESOLVED = "BUSINESS_FACT_UNRESOLVED"
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"
    CONNECTION_REQUIRED = "CONNECTION_REQUIRED"
    ENTITLEMENT_NOT_EFFECTIVE = "ENTITLEMENT_NOT_EFFECTIVE"
    LOCATION_NOT_OPERATIONAL = "LOCATION_NOT_OPERATIONAL"
    LOCATION_PROFILE_MISSING = "LOCATION_PROFILE_MISSING"
    ORGANIZATION_NOT_ACTIVE = "ORGANIZATION_NOT_ACTIVE"
    ORGANIZATION_PROFILE_MISSING = "ORGANIZATION_PROFILE_MISSING"
    RUNTIME_CONTROL_BLOCKED = "RUNTIME_CONTROL_BLOCKED"


# Findings that describe external connection or platform lifecycle state rather
# than something the operator can complete inside onboarding. They stay
# truthfully visible as per-product status; they do not block activation.
NON_ACTIVATION_BLOCKING_CODES: frozenset[ReadinessCode] = frozenset(
    {
        ReadinessCode.CONNECTION_REQUIRED,
        ReadinessCode.ORGANIZATION_NOT_ACTIVE,
        ReadinessCode.ENTITLEMENT_NOT_EFFECTIVE,
    }
)


# Where each finding is resolved. Exhaustive over ReadinessCode — the test suite
# asserts that, so a new code cannot ship without a destination.
RESOLUTIONS: dict[ReadinessCode, BlockerResolution] = {
    ReadinessCode.ORGANIZATION_PROFILE_MISSING: BlockerResolution(
        step_key="organization_profile",
        route="/onboarding",
        control="organization-profile",
        permission="profiles.update",
        label="Create the organization profile",
    ),
    ReadinessCode.LOCATION_NOT_OPERATIONAL: BlockerResolution(
        step_key="locations",
        route="/onboarding",
        control="locations",
        permission="locations.lifecycle.manage",
        label="Select an eligible location",
    ),
    ReadinessCode.LOCATION_PROFILE_MISSING: BlockerResolution(
        step_key="locations",
        route="/onboarding",
        control="location-profile",
        permission="profiles.update",
        label="Complete the location profile",
    ),
    ReadinessCode.CONFIGURATION_INVALID: BlockerResolution(
        step_key=None,
        route="/settings",
        control="configuration",
        permission="configuration.manage",
        label="Activate a valid configuration revision",
    ),
    ReadinessCode.BUSINESS_FACT_UNRESOLVED: BlockerResolution(
        step_key=None,
        route="/onboarding",
        control="business-facts",
        permission="business_facts.approve",
        label="Confirm the business details",
    ),
    ReadinessCode.APPROVAL_POLICY_MISSING: BlockerResolution(
        step_key=None,
        route="/onboarding",
        control="approval-policy",
        permission="policies.manage",
        label="Provision the default approval policy",
    ),
    ReadinessCode.RUNTIME_CONTROL_BLOCKED: BlockerResolution(
        step_key=None,
        route="/settings",
        control="runtime-controls",
        permission="runtime_controls.manage",
        label="Clear the runtime control blocking this product",
    ),
    # The three non-activation-blocking codes still need a destination, because
    # they remain visible as per-product status and the operator still has to
    # act on them eventually — just not to activate.
    ReadinessCode.CONNECTION_REQUIRED: BlockerResolution(
        step_key=None,
        route="/integrations",
        control="connections",
        # Connecting a provider reaches outside the platform, so it is
        # deliberately outside the onboarding setup surface and is expected to
        # be unresolvable until the client is active.
        permission=None,
        label="Connect the required integration",
    ),
    ReadinessCode.ENTITLEMENT_NOT_EFFECTIVE: BlockerResolution(
        step_key="products",
        route="/onboarding",
        control="products",
        permission="products.entitlements.manage",
        label="Enable this product",
    ),
    ReadinessCode.ORGANIZATION_NOT_ACTIVE: BlockerResolution(
        step_key=None,
        route="/onboarding",
        control="activate",
        permission="onboarding.manage",
        label="Activate the client",
    ),
}


def finding(
    code: ReadinessCode,
    *,
    blocking: bool = True,
    resource_key: str | None = None,
    remediation: str | None = None,
) -> ReadinessFinding:
    """Build a finding with its resolution attached.

    Going through this factory is what guarantees a finding cannot be emitted
    without a destination. ``remediation`` defaults to the registry label and is
    passed explicitly only where the sentence varies at runtime.
    """
    resolution = RESOLUTIONS[code]
    return ReadinessFinding(
        code=code.value,
        blocking=blocking,
        resource_key=resource_key,
        remediation=remediation if remediation is not None else f"{resolution.label}.",
        resolution=resolution,
    )
