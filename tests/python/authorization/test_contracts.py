"""Immutable authorization request and decision contracts."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from apps.api.app.access_control.catalog import PERMISSION_CATALOG
from apps.api.app.access_control.enums import ScopeType
from apps.api.app.administration.catalog import PRODUCT_CATALOG
from apps.api.app.administration.enums import EntitlementStatus
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision, AuthorizationRequest
from apps.api.app.authorization.entitlements import (
    EFFECTIVE_ENTITLEMENT_STATUSES,
    PRODUCT_PERMISSION_TO_PRODUCT,
    ProductEntitlementAuthorizationContext,
    product_key_for_permission,
)
from apps.api.app.authorization.enums import AuthorizationReason
from apps.api.app.authorization.service import assurance_satisfies, scope_applies


def test_request_contract_is_exact_frozen_and_scope_safe() -> None:
    user_id, organization_id, location_id = uuid4(), uuid4(), uuid4()
    request = AuthorizationRequest(
        platform_user_id=user_id,
        organization_id=organization_id,
        permission_key="organization.read",
        resource_scope=ScopeType.ORGANIZATION,
    )
    assert request.minimum_assurance_level is AssuranceLevel.AAL1
    with pytest.raises(ValidationError):
        request.permission_key = "locations.read"
    with pytest.raises(ValidationError):
        AuthorizationRequest(
            platform_user_id=user_id,
            organization_id=organization_id,
            permission_key="locations.read",
            resource_scope=ScopeType.ORGANIZATION,
            location_id=location_id,
        )
    with pytest.raises(ValidationError):
        AuthorizationRequest(
            platform_user_id=user_id,
            organization_id=organization_id,
            permission_key="locations.read",
            resource_scope=ScopeType.LOCATION,
        )
    with pytest.raises(ValidationError):
        AuthorizationRequest.model_validate({**request.model_dump(), "role_keys": ["owner"]})


def test_decision_is_internal_immutable_and_scope_and_aal_rules_are_exact() -> None:
    decision = AuthorizationDecision(
        allowed=False,
        organization_id=uuid4(),
        platform_user_id=uuid4(),
        membership_id=None,
        permission_key="organization.read",
        resource_scope=ScopeType.ORGANIZATION,
        location_id=None,
        assurance_level=AssuranceLevel.AAL1,
        minimum_assurance_level=AssuranceLevel.AAL2,
        reason_code=AuthorizationReason.INSUFFICIENT_ASSURANCE,
    )
    assert set(decision.model_dump()) == {
        "allowed",
        "organization_id",
        "platform_user_id",
        "membership_id",
        "permission_key",
        "resource_scope",
        "location_id",
        "assurance_level",
        "minimum_assurance_level",
        "applicable_role_assignment_ids",
        "applicable_deny_ids",
        "reason_code",
    }
    assert assurance_satisfies(AssuranceLevel.AAL1, AssuranceLevel.AAL1)
    assert assurance_satisfies(AssuranceLevel.AAL2, AssuranceLevel.AAL1)
    assert assurance_satisfies(AssuranceLevel.AAL2, AssuranceLevel.AAL2)
    assert not assurance_satisfies(AssuranceLevel.AAL1, AssuranceLevel.AAL2)
    location_id = uuid4()
    assert scope_applies(ScopeType.ORGANIZATION, None, ScopeType.LOCATION, location_id)
    assert scope_applies(ScopeType.LOCATION, location_id, ScopeType.LOCATION, location_id)
    assert not scope_applies(ScopeType.LOCATION, location_id, ScopeType.ORGANIZATION, None)


def test_permission_to_product_mapping_is_exact_complete_and_not_route_inferred() -> None:
    expected = {
        permission_key: resource
        for permission_key, (_, _, resource, _) in PERMISSION_CATALOG.items()
        if resource in PRODUCT_CATALOG
    }
    assert dict(PRODUCT_PERMISSION_TO_PRODUCT) == expected
    assert product_key_for_permission("gbp.read") == "gbp"
    assert product_key_for_permission("gbp.unregistered") is None
    assert product_key_for_permission("organization.read") is None


def test_entitlement_effectiveness_and_location_scope_fail_closed() -> None:
    now = datetime.now(UTC)
    location_id, other_location_id = uuid4(), uuid4()
    entitlement_id = uuid4()

    def context(
        status: str,
        *,
        effective_from: datetime | None = None,
        effective_until: datetime | None = None,
        has_location_scope: bool = False,
        active_location_ids: frozenset[UUID] = frozenset(),
    ) -> ProductEntitlementAuthorizationContext:
        return ProductEntitlementAuthorizationContext(
            catalog_consistent=True,
            entitlement_id=entitlement_id,
            status=status,
            effective_from=effective_from or now - timedelta(days=1),
            effective_until=effective_until,
            has_location_scope=has_location_scope,
            active_location_ids=active_location_ids,
        )

    expected_effective = {
        EntitlementStatus.SETUP_REQUIRED.value,
        EntitlementStatus.CONFIGURATION_REQUIRED.value,
        EntitlementStatus.CONNECTION_REQUIRED.value,
        EntitlementStatus.READY.value,
        EntitlementStatus.ACTIVE.value,
        EntitlementStatus.PAUSED.value,
        EntitlementStatus.DEGRADED.value,
    }
    assert expected_effective == EFFECTIVE_ENTITLEMENT_STATUSES
    for status in EntitlementStatus:
        entitlement = context(status.value)
        assert entitlement.authorizes(ScopeType.ORGANIZATION, None, now=now) is (
            status.value in expected_effective
        )

    assert not context(
        EntitlementStatus.ACTIVE.value,
        effective_from=now + timedelta(seconds=1),
    ).authorizes(ScopeType.ORGANIZATION, None, now=now)
    assert not context(
        EntitlementStatus.ACTIVE.value,
        effective_until=now,
    ).authorizes(ScopeType.ORGANIZATION, None, now=now)

    restricted = context(
        EntitlementStatus.ACTIVE.value,
        has_location_scope=True,
        active_location_ids=frozenset({location_id}),
    )
    assert restricted.authorizes(ScopeType.LOCATION, location_id, now=now)
    assert not restricted.authorizes(ScopeType.LOCATION, other_location_id, now=now)
    assert not restricted.authorizes(ScopeType.ORGANIZATION, None, now=now)
    assert not context(
        EntitlementStatus.ACTIVE.value,
        has_location_scope=True,
    ).authorizes(ScopeType.LOCATION, location_id, now=now)
