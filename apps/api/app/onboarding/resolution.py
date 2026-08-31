"""Where each onboarding step is completed.

The step half of the same idea as ``administration.readiness_codes``: a step's
remedy used to be a `next_action` sentence with no destination, so the operator
read "Mark one location as the primary location" and then had to work out where
that control lives. Each step now declares its route, its control and the
permission that completes it, and the deadlock-freedom suite asserts every one
of those permissions is available while the client is still onboarding.
"""

from apps.api.app.administration.contracts import BlockerResolution

# Keyed by the step keys in ``onboarding.service._ALL_STEP_KEYS``. Exhaustive —
# ``tests/python/onboarding/test_deadlock_freedom.py`` asserts the two agree.
STEP_RESOLUTIONS: dict[str, BlockerResolution] = {
    "organization_profile": BlockerResolution(
        step_key="organization_profile",
        route="/onboarding",
        control="organization-profile",
        permission="organization.update",
        label="Create the organization profile",
    ),
    "locations": BlockerResolution(
        step_key="locations",
        route="/onboarding",
        control="locations",
        permission="locations.create",
        label="Add a business location",
    ),
    "primary_location": BlockerResolution(
        step_key="primary_location",
        route="/onboarding",
        control="locations",
        permission="locations.update",
        label="Mark a location primary",
    ),
    "website_domain": BlockerResolution(
        step_key="website_domain",
        route="/onboarding",
        control="website-domain",
        permission="organization.settings.manage",
        label="Add the primary website domain",
    ),
    "industry": BlockerResolution(
        step_key="industry",
        route="/onboarding",
        control="industry",
        permission="organization.update",
        label="Select the industry",
    ),
    # Services are assigned on the Administration page, not in onboarding. This
    # points there rather than at a section of /onboarding that does not exist —
    # a destination that does not resolve is the same dead end as no destination.
    "services": BlockerResolution(
        step_key="services",
        route="/administration",
        control="services",
        permission="services.manage",
        label="Assign the services",
    ),
    "users": BlockerResolution(
        step_key="users",
        route="/onboarding",
        control="users",
        permission="organization.members.manage",
        label="Give someone access",
    ),
    "products": BlockerResolution(
        step_key="products",
        route="/onboarding",
        control="products",
        permission="products.entitlements.manage",
        label="Enable the products",
    ),
}
