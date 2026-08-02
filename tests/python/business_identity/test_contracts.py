"""Exact immutable business-identity contract tests."""

import pytest
from pydantic import ValidationError

from apps.api.app.business_identity.contracts import (
    LocationBusinessIdentity,
    LocationIdentity,
    LocationProfileIdentity,
    OrganizationBusinessIdentity,
    OrganizationIdentity,
    OrganizationProfileIdentity,
)


def test_contract_fields_are_exact_and_exclude_unapproved_aggregation() -> None:
    assert set(OrganizationBusinessIdentity.model_fields) == {
        "organization",
        "industry",
        "organization_profile",
        "has_industry",
        "has_organization_profile",
    }
    assert set(LocationBusinessIdentity.model_fields) == {
        *OrganizationBusinessIdentity.model_fields,
        "location",
        "location_profile",
        "has_location_profile",
        "resolved_call_to_action",
    }
    assert set(OrganizationIdentity.model_fields) == {
        "id",
        "name",
        "slug",
        "organization_type",
        "status",
        "timezone",
        "default_currency",
        "version",
    }
    assert set(LocationIdentity.model_fields) == {
        "id",
        "organization_id",
        "name",
        "slug",
        "location_type",
        "status",
        "timezone",
        "country_code",
        "is_primary",
        "version",
    }
    for prohibited in ("groups", "effective_services", "effective_claims", "metadata"):
        assert prohibited not in LocationBusinessIdentity.model_fields


def test_profile_lists_remain_source_specific_and_immutable() -> None:
    assert "primary_services" in OrganizationProfileIdentity.model_fields
    assert "primary_services" in LocationProfileIdentity.model_fields
    assert "effective_primary_services" not in LocationBusinessIdentity.model_fields
    assert OrganizationBusinessIdentity.model_config["frozen"] is True


def test_contracts_forbid_unapproved_fields() -> None:
    with pytest.raises(ValidationError):
        OrganizationBusinessIdentity.model_validate({"unexpected": True})
