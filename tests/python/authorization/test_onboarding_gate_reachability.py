"""Every gate that blocks activation must be openable before activation.

Three deadlocks reached production in one afternoon, all the same shape: the
platform demanded something of the operator and refused them the means to do it.
Each was found by a person hitting it, and each was patched alone, which is why
there was always another one behind it.

This is the check that should have existed instead.

It used to carry its own copy of the code-to-permission mapping and recover the
emitted codes by regex over the administration service's source. Both of those
were workarounds for the same missing thing: the codes were bare strings, so
neither the set of them nor their resolutions existed anywhere a test could read.
They do now — ``ReadinessCode`` closes the set and ``RESOLUTIONS`` says where
each one is resolved — so this reads the real registry instead of a second copy
that could drift from it.

The regex is kept for one narrow job: proving nothing bypasses the factory and
re-introduces an unregistered code.
"""

import re
from pathlib import Path

import pytest

from apps.api.app.administration.readiness_codes import (
    NON_ACTIVATION_BLOCKING_CODES,
    RESOLUTIONS,
    ReadinessCode,
)
from apps.api.app.authorization.onboarding_scope import organization_permits
from apps.api.app.onboarding.service import _NON_ACTIVATION_BLOCKING_CODES
from apps.api.app.organizations.enums import OrganizationStatus

SERVICE_SOURCE = (
    Path(__file__).resolve().parents[3] / "apps" / "api" / "app" / "administration" / "service.py"
)


def test_no_finding_bypasses_the_resolution_registry() -> None:
    """A raw ``code="..."`` literal is a finding with no destination.

    Findings are built through ``readiness_codes.finding()``, which attaches the
    resolution. Constructing a ``ReadinessFinding`` directly with a string code
    would skip that and put an unactionable blocker back in front of an operator.
    """
    literals = set(re.findall(r'code="([A-Z_]+)"', SERVICE_SOURCE.read_text(encoding="utf-8")))
    assert literals == set(), (
        "these findings are built with a raw code string instead of the "
        f"finding() factory, so they carry no resolution: {sorted(literals)}"
    )


def test_every_code_has_a_resolution() -> None:
    # A new blocking finding with no entry here is not a test failure to route
    # around: it means nobody decided whether an operator can clear it.
    unclassified = {code.value for code in ReadinessCode if code not in RESOLUTIONS}
    assert unclassified == set(), (
        f"readiness codes with no resolving permission recorded: {sorted(unclassified)}"
    )


def test_no_stale_classifications_linger() -> None:
    removed = {code.value for code in RESOLUTIONS if code not in set(ReadinessCode)}
    assert removed == set(), f"codes no longer emitted: {sorted(removed)}"


@pytest.mark.parametrize("code", sorted(ReadinessCode))
def test_an_activation_blocker_can_be_cleared_before_activation(code: ReadinessCode) -> None:
    """The rule the allowlist follows, enforced rather than trusted.

    The permissions here are the ones the routes actually require — checked
    against the route decorators, not inferred from the name of the thing being
    fixed. An earlier draft of the registry guessed ``organization.update`` for
    the organization profile and ``locations.update`` for the location profile;
    both routes in fact require ``profiles.update``, so the guess would have
    asserted the wrong permission was reachable and passed while the real
    deadlock stayed open.
    """
    if code in NON_ACTIVATION_BLOCKING_CODES:
        pytest.skip(f"{code.value} does not block activation")
    permission = RESOLUTIONS[code].permission
    assert permission is not None, (
        f"{code.value} blocks activation but names no permission that clears it"
    )
    assert organization_permits(OrganizationStatus.ONBOARDING, permission), (
        f"{code.value} blocks activation but {permission} is refused while onboarding — "
        "the platform would demand this and forbid the fix"
    )


def test_the_codes_excluded_from_activation_are_the_ones_we_think() -> None:
    # If a code is removed from that exclusion set it starts blocking
    # activation, and this file must then prove it is clearable.
    assert (
        frozenset({"CONNECTION_REQUIRED", "ORGANIZATION_NOT_ACTIVE", "ENTITLEMENT_NOT_EFFECTIVE"})
        == _NON_ACTIVATION_BLOCKING_CODES
    )


def test_the_onboarding_service_and_the_registry_agree_on_the_exclusions() -> None:
    """One set, read two ways, so the two modules cannot drift apart."""
    assert (
        frozenset(code.value for code in NON_ACTIVATION_BLOCKING_CODES)
        == _NON_ACTIVATION_BLOCKING_CODES
    )
