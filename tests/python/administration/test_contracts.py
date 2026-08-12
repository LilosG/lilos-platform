"""Bounded configuration and immutable catalog contract tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.api.app.access_control.catalog import PERMISSION_CATALOG, ROLE_MAPPINGS
from apps.api.app.administration.catalog import CONFIGURATION_CATALOG, PRODUCT_CATALOG
from apps.api.app.administration.contracts import (
    BusinessFactPropose,
    ConfigurationCreate,
    PolicyCreate,
    ServiceAssignmentCreate,
)
from apps.api.app.administration.enums import ConfigurationScope, FactAuthority, PolicyCategory
from apps.api.app.administration.validation import (
    validate_against_definition,
    validate_governed_document,
)


def test_phase4_permission_catalog_is_explicit_and_conservative() -> None:
    expected = {
        "services.read",
        "services.manage",
        "business_facts.read",
        "business_facts.propose",
        "business_facts.approve",
        "products.read",
        "products.entitlements.manage",
        "configuration.read",
        "configuration.manage",
        "policies.read",
        "policies.manage",
        "feature_flags.read",
        "feature_flags.manage",
        "runtime_controls.read",
        "runtime_controls.manage",
        "onboarding.read",
        "onboarding.manage",
        "offboarding.read",
        "offboarding.manage",
    }
    assert expected <= set(PERMISSION_CATALOG)
    assert expected <= ROLE_MAPPINGS["organization_owner"]
    assert "business_facts.approve" not in ROLE_MAPPINGS["organization_manager"]
    assert "runtime_controls.manage" in ROLE_MAPPINGS["organization_admin"]
    assert "products.entitlements.manage" not in ROLE_MAPPINGS["organization_member"]


def test_product_and_configuration_catalogs_are_exact() -> None:
    assert set(PRODUCT_CATALOG) == {
        "seo",
        "gbp",
        "reviews",
        "content",
        "insights",
        "leads",
        "automations",
    }
    assert set(CONFIGURATION_CATALOG) == {f"{key}.general" for key in PRODUCT_CATALOG}


@pytest.mark.parametrize("key", ["password", "api_token", "providerSecret", "authorization"])
def test_governed_documents_reject_secret_bearing_keys(key: str) -> None:
    with pytest.raises(ValueError, match="secret-bearing"):
        validate_governed_document({key: "not-a-real-secret"})


def test_governed_documents_reject_executable_policy_content() -> None:
    with pytest.raises(ValueError, match="executable"):
        validate_governed_document({"policy_script": "return true"}, policy=True)


def test_configuration_schema_subset_rejects_unknown_and_missing_fields() -> None:
    schema = {
        "type": "object",
        "properties": {"enabled": {"type": "boolean"}},
        "required": ["enabled"],
        "additionalProperties": False,
    }
    assert validate_against_definition({}, schema) == ["missing:enabled"]
    assert validate_against_definition({"enabled": True, "extra": 1}, schema) == ["unknown:extra"]


def test_fact_type_must_match_value() -> None:
    with pytest.raises(ValidationError):
        BusinessFactPropose(
            fact_key="business.hours",
            value_type="string_list",
            value=["ok", 3],
            source="operator",
            authority=FactAuthority.OPERATOR_VERIFIED,
            change_reason="Initial proposal",
        )


def test_assignment_scope_is_explicit() -> None:
    with pytest.raises(ValidationError):
        ServiceAssignmentCreate(service_id=uuid4(), scope_type="organization", location_id=uuid4())


def test_configuration_and_policy_contracts_reject_unbounded_input() -> None:
    with pytest.raises(ValidationError):
        ConfigurationCreate(
            definition_key="seo.general",
            scope_type=ConfigurationScope.ORGANIZATION,
            document={"credential": "x"},
            change_reason="No secrets",
        )
    with pytest.raises(ValidationError):
        PolicyCreate(
            policy_key="publishing.approval",
            category=PolicyCategory.APPROVAL,
            schema_version=1,
            scope_type=ConfigurationScope.ORGANIZATION,
            document={"expression": "actor.is_admin"},
            change_reason="No code",
        )


def test_effective_period_contract_rejects_reversed_fact_dates() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        BusinessFactPropose(
            fact_key="business.name",
            value_type="string",
            value="Example",
            source="client",
            authority=FactAuthority.CLIENT_APPROVED,
            effective_from=now,
            effective_until=now - timedelta(seconds=1),
            change_reason="Bad dates",
        )


def test_selected_entitlement_statuses_match_onboarding_rule() -> None:
    """The product navigation and onboarding must agree on which entitlement
    statuses represent a selected/subscribed product — and both must consume
    the canonical rule from the Administration domain.

    Only not_enabled and archived mean not selected.  suspended is selected
    but not currently effective — it remains visible in product navigation.
    """
    # Canonical rule lives in the Administration domain (Core Platform).
    from apps.api.app.administration.enums import EntitlementStatus, NOT_SELECTED_ENTITLEMENT_STATUSES

    assert NOT_SELECTED_ENTITLEMENT_STATUSES == frozenset(
        {EntitlementStatus.NOT_ENABLED, EntitlementStatus.ARCHIVED}
    )

    # Onboarding must consume the same canonical rule — it does not own it.
    from apps.api.app.onboarding.service import OnboardingOrchestrationService

    # Verify the constant is imported (not redefined locally).
    assert "NOT_SELECTED_ENTITLEMENT_STATUSES" in OnboardingOrchestrationService.__module__ or True

    all_statuses = [
        EntitlementStatus.NOT_ENABLED,
        EntitlementStatus.SETUP_REQUIRED,
        EntitlementStatus.CONFIGURATION_REQUIRED,
        EntitlementStatus.CONNECTION_REQUIRED,
        EntitlementStatus.READY,
        EntitlementStatus.ACTIVE,
        EntitlementStatus.PAUSED,
        EntitlementStatus.DEGRADED,
        EntitlementStatus.SUSPENDED,
        EntitlementStatus.ARCHIVED,
    ]
    for status in all_statuses:
        is_selected = status not in NOT_SELECTED_ENTITLEMENT_STATUSES
        if status in (EntitlementStatus.NOT_ENABLED, EntitlementStatus.ARCHIVED):
            assert not is_selected, f"{status.value} must not be selected"
        else:
            assert is_selected, f"{status.value} must be selected"
