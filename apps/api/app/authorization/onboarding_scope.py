"""What a client can be configured with before it is activated.

Authorization refused every permission unless the organization was ACTIVE. That
made onboarding impossible to complete: activation is blocked until business
details are confirmed, and confirming them was itself refused with "This client
is not active yet. Finish onboarding activation before connecting providers or
running product work." Activation required the facts, the facts required
activation, and nothing in the product broke the tie.

An organization in ONBOARDING is being set up on purpose, so the setup
permissions must work. This is the bounded set that must: reading and shaping
the client's own record, its locations, its business facts, its onboarding
state, its product selection and governance policy.

It deliberately excludes everything that reaches outside the platform or that
publishes on a client's behalf — provider authorization, resource mapping,
publication. Those stay gated on activation, which is what the product already
tells the operator: "Provider authorization and resource mapping are
intentionally completed in the standard organization workspace after
activation." An unactivated client can be configured; it cannot act.
"""

from apps.api.app.organizations.enums import OrganizationStatus

# The rule this set follows, so it is derived rather than guessed at: any
# permission whose absence can block activation must be usable before
# activation. Otherwise the platform demands something of the operator and
# refuses them the means to do it — which is how three separate deadlocks
# reached production in one afternoon. test_onboarding_gate_reachability walks
# every blocking readiness code the administration service can emit and fails
# if the permission that resolves it is missing here.
ONBOARDING_SETUP_PERMISSIONS: frozenset[str] = frozenset(
    {
        # The client's own record and who may work on it.
        "organization.read",
        "organization.update",
        "organization.settings.manage",
        "organization.members.manage",
        "organization.invitations.manage",
        "organization.roles.manage",
        # Locations, including the location profile that SEO readiness requires.
        "locations.read",
        "locations.create",
        "locations.update",
        "locations.lifecycle.manage",
        "locations.groups.manage",
        # The business facts activation is blocked on. Approving one is a
        # governance decision, not an external action, and it is precisely what
        # the operator is being asked for at this point.
        "business_facts.read",
        "business_facts.propose",
        "business_facts.approve",
        # The organization and location profiles. LOCATION_PROFILE_MISSING and
        # ORGANIZATION_PROFILE_MISSING are both blocking readiness findings, so
        # without these the client is told to create a profile it is not allowed
        # to create.
        "profiles.read",
        "profiles.update",
        # The onboarding read model and the steps themselves.
        "onboarding.read",
        "onboarding.manage",
        # CONFIGURATION_INVALID blocks activation, and the fix is to activate a
        # valid configuration revision.
        "configuration.read",
        "configuration.manage",
        # RUNTIME_CONTROL_BLOCKED blocks activation, and the fix is to resolve
        # the winning control.
        "runtime_controls.read",
        "runtime_controls.manage",
        # Product selection and the services/policies a product's readiness
        # depends on. Selecting a product is not using it.
        "products.read",
        "products.entitlements.manage",
        "services.read",
        "services.manage",
        "policies.read",
        "policies.manage",
    }
)


def organization_permits(status: OrganizationStatus, permission_key: str) -> bool:
    """Return True when this organization state allows this permission.

    An active client permits everything its members are granted. A client still
    onboarding permits only the setup surface above, so it can be configured
    without being able to act. Every other state — prospect, paused, suspended,
    offboarding, archived — permits nothing, unchanged.
    """
    if status is OrganizationStatus.ACTIVE:
        return True
    if status is OrganizationStatus.ONBOARDING:
        return permission_key in ONBOARDING_SETUP_PERMISSIONS
    return False
