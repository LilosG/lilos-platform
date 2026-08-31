"""Every gate that blocks activation must be openable before activation.

Three deadlocks reached production in one afternoon, all the same shape: the
platform demanded something of the operator and refused them the means to do it.
Each was found by a person hitting it, and each was patched alone, which is why
there was always another one behind it.

This is the check that should have existed instead. It reads the blocking
readiness codes straight out of the administration service, maps each to the
permission that resolves it, and fails if that permission cannot be used while
the client is still onboarding. A new blocking code with no mapping fails too,
so the classification cannot be skipped by whoever adds the next one.
"""

import re
from pathlib import Path

import pytest

from apps.api.app.authorization.onboarding_scope import organization_permits
from apps.api.app.onboarding.service import _NON_ACTIVATION_BLOCKING_CODES
from apps.api.app.organizations.enums import OrganizationStatus

SERVICE_SOURCE = (
    Path(__file__).resolve().parents[3] / "apps" / "api" / "app" / "administration" / "service.py"
)

# The permission an operator needs to clear each blocking readiness finding.
# None means the finding is not cleared by a per-organization permission at all
# — the reason is recorded beside it.
RESOLVING_PERMISSION: dict[str, str | None] = {
    "ORGANIZATION_PROFILE_MISSING": "profiles.update",
    "LOCATION_PROFILE_MISSING": "profiles.update",
    "LOCATION_NOT_OPERATIONAL": "locations.lifecycle.manage",
    "BUSINESS_FACT_UNRESOLVED": "business_facts.approve",
    "APPROVAL_POLICY_MISSING": "policies.manage",
    "CONFIGURATION_INVALID": "configuration.manage",
    "RUNTIME_CONTROL_BLOCKED": "runtime_controls.manage",
    "ONBOARDING_BLOCKED": "onboarding.manage",
    # Cleared by activating, which is the thing being gated; excluded from
    # activation blockers by the onboarding service for exactly that reason.
    "ORGANIZATION_NOT_ACTIVE": None,
    # Connecting a provider is deliberately post-activation, and the onboarding
    # service does not count it against activation.
    "CONNECTION_REQUIRED": None,
    # Selecting a product is permitted during onboarding, and this code is not
    # counted against activation either.
    "ENTITLEMENT_NOT_EFFECTIVE": "products.entitlements.manage",
}


def emitted_readiness_codes() -> set[str]:
    """Every finding code the administration service can produce."""
    source = SERVICE_SOURCE.read_text(encoding="utf-8")
    return set(re.findall(r'code="([A-Z_]+)"', source))


def test_every_emitted_code_is_classified() -> None:
    # A new blocking finding with no entry here is not a test failure to route
    # around: it means nobody decided whether an operator can clear it.
    unclassified = emitted_readiness_codes() - set(RESOLVING_PERMISSION)
    assert unclassified == set(), (
        f"readiness codes with no resolving permission recorded: {sorted(unclassified)}"
    )


def test_no_stale_classifications_linger() -> None:
    removed = set(RESOLVING_PERMISSION) - emitted_readiness_codes()
    assert removed == set(), f"codes no longer emitted: {sorted(removed)}"


@pytest.mark.parametrize(
    "code",
    sorted(code for code, permission in RESOLVING_PERMISSION.items() if permission),
)
def test_an_activation_blocker_can_be_cleared_before_activation(code: str) -> None:
    """The rule the allowlist follows, enforced rather than trusted."""
    if code in _NON_ACTIVATION_BLOCKING_CODES:
        pytest.skip(f"{code} does not block activation")
    permission = RESOLVING_PERMISSION[code]
    assert permission is not None
    assert organization_permits(OrganizationStatus.ONBOARDING, permission), (
        f"{code} blocks activation but {permission} is refused while onboarding — "
        "the platform would demand this and forbid the fix"
    )


def test_the_codes_excluded_from_activation_are_the_ones_we_think() -> None:
    # If a code is removed from that exclusion set it starts blocking
    # activation, and this file must then prove it is clearable.
    assert (
        frozenset({"CONNECTION_REQUIRED", "ORGANIZATION_NOT_ACTIVE", "ENTITLEMENT_NOT_EFFECTIVE"})
        == _NON_ACTIVATION_BLOCKING_CODES
    )
