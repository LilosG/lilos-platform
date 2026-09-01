"""A client being onboarded can be configured, but cannot act.

The deadlock this breaks: authorization refused every permission unless the
organization was ACTIVE, so confirming the business facts that activation is
blocked on was itself refused with "This client is not active yet. Finish
onboarding activation before connecting providers or running product work."
Activation needed the facts; the facts needed activation.
"""

import pytest

from apps.api.app.authorization.onboarding_scope import (
    ONBOARDING_SETUP_PERMISSIONS,
    organization_permits,
)
from apps.api.app.organizations.enums import OrganizationStatus


class TestActiveClients:
    @pytest.mark.parametrize(
        "permission",
        ["organization.read", "gbp.publish", "business_facts.approve", "anything.at_all"],
    )
    def test_an_active_client_permits_everything_its_members_are_granted(
        self, permission: str
    ) -> None:
        assert organization_permits(OrganizationStatus.ACTIVE, permission) is True


class TestOnboardingClients:
    @pytest.mark.parametrize(
        "permission",
        [
            # The exact permissions the blocked activation asked the operator for.
            "business_facts.read",
            "business_facts.propose",
            "business_facts.approve",
            "locations.create",
            "locations.update",
            "onboarding.read",
            "onboarding.manage",
            "organization.settings.manage",
            "products.entitlements.manage",
            "gbp.read",
            "gbp.connect",
            "integrations.read",
            "integrations.connect",
        ],
    )
    def test_setup_work_is_permitted_while_onboarding(self, permission: str) -> None:
        assert organization_permits(OrganizationStatus.ONBOARDING, permission) is True

    @pytest.mark.parametrize(
        "permission",
        [
            "gbp.publish",
            "gbp.propose",
            "reviews.publish",
            "content.publish",
            "seo.manage",
        ],
    )
    def test_acting_on_a_client_is_still_refused_while_onboarding(self, permission: str) -> None:
        # Provider writes, publication, and product execution stay gated on
        # activation. Read-only provider setup is covered above.
        assert organization_permits(OrganizationStatus.ONBOARDING, permission) is False

    def test_an_unknown_permission_is_refused_rather_than_assumed_safe(self) -> None:
        assert organization_permits(OrganizationStatus.ONBOARDING, "future.capability") is False


class TestEveryOtherState:
    @pytest.mark.parametrize(
        "status",
        [
            OrganizationStatus.PROSPECT,
            OrganizationStatus.PAUSED,
            OrganizationStatus.SUSPENDED,
            OrganizationStatus.OFFBOARDING,
            OrganizationStatus.ARCHIVED,
        ],
    )
    def test_they_permit_nothing_including_setup(self, status: OrganizationStatus) -> None:
        # Only onboarding gains a setup surface. A paused or suspended client
        # must not become editable as a side effect of this change.
        assert organization_permits(status, "organization.read") is False
        assert organization_permits(status, "business_facts.approve") is False


def test_the_setup_surface_grants_source_collection_but_not_provider_writes() -> None:
    # A guard against the bounded read/setup surface quietly growing into
    # publication or product execution.
    for permission in ONBOARDING_SETUP_PERMISSIONS:
        domain = permission.split(".", 1)[0]
        assert domain in {
            "organization",
            "locations",
            "business_facts",
            "profiles",
            "onboarding",
            "configuration",
            "runtime_controls",
            "products",
            "services",
            "policies",
            "integrations",
            "gbp",
        }, permission
        assert "publish" not in permission
        assert permission not in {
            "gbp.propose",
            "gbp.approve",
            "gbp.publish",
        }
