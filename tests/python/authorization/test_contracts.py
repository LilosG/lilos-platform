"""Immutable authorization request and decision contracts."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision, AuthorizationRequest
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
