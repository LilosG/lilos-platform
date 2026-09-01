"""Deadlock freedom: everything shown to an operator must be clearable by them.

Onboarding kept deadlocking in production, and each deadlock was found by hand,
one client at a time. The reason no test caught them is that "can the operator
being shown this blocker actually resolve it?" was not a property the code could
express, let alone assert — a blocker was a bare sentence.

Now that a blocker carries its resolution, the property is checkable. These
tests assert it over the whole registry rather than over the instances someone
happened to hit, so the *class* of bug fails in CI.

The specific deadlock that shipped: authorization refused every permission
unless the organization was ACTIVE, activation was blocked until business facts
were confirmed, and confirming them needed `business_facts.approve` — which was
refused because the client was not active. `test_every_onboarding_blocker_is_
resolvable_during_onboarding` fails on that arrangement.
"""

from apps.api.app.administration.readiness_codes import (
    NON_ACTIVATION_BLOCKING_CODES,
    RESOLUTIONS,
    ReadinessCode,
)
from apps.api.app.authorization.onboarding_scope import (
    ONBOARDING_SETUP_PERMISSIONS,
    organization_permits,
)
from apps.api.app.onboarding.resolution import STEP_RESOLUTIONS
from apps.api.app.onboarding.service import _ALL_STEP_KEYS
from apps.api.app.organizations.enums import OrganizationStatus

# ---------------------------------------------------------------------------
# The registry is exhaustive
# ---------------------------------------------------------------------------


def test_every_readiness_code_declares_where_it_is_resolved() -> None:
    """A finding without a destination is the bug this whole change exists to stop."""
    missing = [code for code in ReadinessCode if code not in RESOLUTIONS]
    assert not missing, (
        "These readiness codes can be shown to an operator with no way to act on "
        f"them: {[c.value for c in missing]}. Add each to RESOLUTIONS."
    )


def test_resolution_registry_has_no_entries_for_codes_that_do_not_exist() -> None:
    stale = [code for code in RESOLUTIONS if code not in set(ReadinessCode)]
    assert not stale, f"RESOLUTIONS references codes that no longer exist: {stale}"


def test_every_resolution_names_a_route_and_a_control() -> None:
    for code, resolution in RESOLUTIONS.items():
        assert resolution.route.startswith("/"), (
            f"{code.value} has route {resolution.route!r}, which is not a path the "
            "frontend can navigate to."
        )
        assert resolution.control, (
            f"{code.value} names no control, so the operator lands on "
            f"{resolution.route} with nothing to focus."
        )


# ---------------------------------------------------------------------------
# The deadlock-freedom property itself
# ---------------------------------------------------------------------------


def test_every_onboarding_blocker_is_resolvable_during_onboarding() -> None:
    """The property that was violated in production.

    A blocker that stops activation must be clearable while the organization is
    still ONBOARDING. If the permission that clears it is refused in that state,
    the operator is deadlocked: they cannot activate, and they cannot do the
    thing that would let them activate.
    """
    deadlocked: list[str] = []
    for code, resolution in RESOLUTIONS.items():
        if code in NON_ACTIVATION_BLOCKING_CODES:
            continue
        permission = resolution.permission
        assert permission is not None, (
            f"{code.value} blocks activation but declares no permission that "
            "resolves it. Either it does not really block activation (add it to "
            "NON_ACTIVATION_BLOCKING_CODES) or it needs a resolving permission."
        )
        if not organization_permits(OrganizationStatus.ONBOARDING, permission):
            deadlocked.append(f"{code.value} needs {permission}")

    assert not deadlocked, (
        "These blockers stop activation but cannot be resolved while the client "
        f"is still onboarding — an operator hitting one is stuck: {deadlocked}. "
        "Either add the permission to ONBOARDING_SETUP_PERMISSIONS or stop the "
        "finding from blocking activation."
    )


def test_permissions_that_resolve_blockers_are_in_the_onboarding_setup_surface() -> None:
    """Keep the hand-maintained allowlist honest against the registry.

    ONBOARDING_SETUP_PERMISSIONS is written by hand, which is how the original
    deadlock got in. This derives the requirement from the registry instead: any
    permission the product tells an operator to use during onboarding has to be
    one onboarding actually permits.
    """
    required = {
        resolution.permission
        for code, resolution in RESOLUTIONS.items()
        if code not in NON_ACTIVATION_BLOCKING_CODES and resolution.permission is not None
    }
    missing = sorted(required - ONBOARDING_SETUP_PERMISSIONS)
    assert not missing, (
        "ONBOARDING_SETUP_PERMISSIONS is missing permissions the resolution "
        f"registry depends on: {missing}"
    )


def test_external_actions_stay_outside_the_onboarding_setup_surface() -> None:
    """The gate must still be a gate.

    Widening the onboarding surface to break the deadlock must not have widened
    it into publishing or provider authorization. An unactivated client can be
    configured; it must not be able to act on the world.
    """
    forbidden = [
        "gbp.publish",
        "gbp.propose",
        "content.publish",
        "reviews.publish_response",
        "seo.execute",
        "integrations.authorize",
    ]
    leaked = [
        permission
        for permission in forbidden
        if organization_permits(OrganizationStatus.ONBOARDING, permission)
    ]
    assert not leaked, f"An onboarding client can perform external writes it must not: {leaked}"


def test_non_active_non_onboarding_states_permit_nothing() -> None:
    for status in (
        OrganizationStatus.PROSPECT,
        OrganizationStatus.PAUSED,
        OrganizationStatus.SUSPENDED,
        OrganizationStatus.OFFBOARDING,
        OrganizationStatus.ARCHIVED,
    ):
        for permission in sorted(ONBOARDING_SETUP_PERMISSIONS):
            assert not organization_permits(status, permission), (
                f"{status.value} permits {permission}, but only ACTIVE and "
                "ONBOARDING may permit anything."
            )


# ---------------------------------------------------------------------------
# Step resolutions line up with the steps that exist
# ---------------------------------------------------------------------------


def test_resolutions_reference_real_onboarding_steps() -> None:
    unknown = sorted(
        {
            resolution.step_key
            for resolution in RESOLUTIONS.values()
            if resolution.step_key is not None and resolution.step_key not in _ALL_STEP_KEYS
        }
    )
    assert not unknown, (
        f"RESOLUTIONS points at onboarding steps that do not exist: {unknown}. "
        f"Known steps: {list(_ALL_STEP_KEYS)}"
    )


def test_onboarding_blocked_is_not_a_readiness_code() -> None:
    """Product readiness must not restate onboarding blockage back at onboarding.

    Readiness used to emit ONBOARDING_BLOCKED whenever the stored onboarding
    checklist held a blocker. The onboarding read model folds product findings
    into its own blocker list, so the operator was shown "complete blocking
    onboarding requirements" as a blocker on onboarding — once per enabled
    product, clearable only as a side effect of clearing everything else.
    """
    assert "ONBOARDING_BLOCKED" not in {code.value for code in ReadinessCode}


# ---------------------------------------------------------------------------
# The step registry matches the steps, and its permissions work during onboarding
# ---------------------------------------------------------------------------


def test_every_onboarding_step_declares_where_it_is_completed() -> None:
    missing = [key for key in _ALL_STEP_KEYS if key not in STEP_RESOLUTIONS]
    assert not missing, (
        f"These onboarding steps tell the operator what to do but not where: {missing}"
    )


def test_step_registry_has_no_entries_for_steps_that_do_not_exist() -> None:
    stale = sorted(set(STEP_RESOLUTIONS) - set(_ALL_STEP_KEYS))
    assert not stale, f"STEP_RESOLUTIONS references steps that do not exist: {stale}"


def test_every_step_is_completable_while_the_client_is_still_onboarding() -> None:
    """Completing onboarding must be possible during onboarding.

    The same property as the readiness blockers, applied to the steps. Every
    step is by definition something the operator does *before* activation, so
    there is no legitimate reason for any of them to need a permission that
    onboarding refuses.
    """
    stuck = [
        f"{key} needs {resolution.permission}"
        for key, resolution in STEP_RESOLUTIONS.items()
        if resolution.permission is not None
        and not organization_permits(OrganizationStatus.ONBOARDING, resolution.permission)
    ]
    assert not stuck, f"Onboarding steps that cannot be performed during onboarding: {stuck}"


def test_every_step_declares_a_resolving_permission() -> None:
    unowned = sorted(key for key, res in STEP_RESOLUTIONS.items() if res.permission is None)
    assert not unowned, (
        f"These steps name no permission, so nothing can check who may do them: {unowned}"
    )
