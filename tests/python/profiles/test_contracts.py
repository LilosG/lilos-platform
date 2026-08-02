"""Profile field representation, bounds, claims, and defensive-copy tests."""

import pytest
from pydantic import ValidationError

from apps.api.app.profiles.contracts import LocationProfileCreate, OrganizationProfileCreate


def test_collections_are_normalized_copied_and_allow_empty_arrays() -> None:
    services = ["  Service   One  "]
    command = OrganizationProfileCreate(
        primary_services=services,
        approved_claims=[],
        prohibited_claims=[],
    )
    services.append("Caller mutation")
    assert command.primary_services == ["Service One"]
    assert command.approved_claims == []


@pytest.mark.parametrize(
    "payload",
    [
        {"approved_claims": ["Same Claim"], "prohibited_claims": [" same   claim "]},
        {"primary_services": ["Duplicate", "duplicate"]},
        {"primary_services": ["item"] * 51},
        {"primary_services": ["x" * 501]},
        {"primary_services": ["x" * 400 for _ in range(50)]},
        {"brand_name": "x" * 201},
    ],
)
def test_organization_profile_rejects_conflicts_duplicates_and_bounds(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        OrganizationProfileCreate.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"approved_claims": ["Local Claim"], "prohibited_claims": ["local claim"]},
        {"local_references": ["Duplicate", " duplicate "]},
        {"local_landmarks": ["x" * 501]},
        {"local_description": "x" * 8_001},
        {"primary_services": {"uncontrolled": "object"}},
    ],
)
def test_location_profile_rejects_claim_reference_and_shape_violations(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        LocationProfileCreate.model_validate(payload)


def test_profile_contracts_contain_no_generic_or_ai_write_fields() -> None:
    organization_fields = set(OrganizationProfileCreate.model_fields)
    location_fields = set(LocationProfileCreate.model_fields)
    prohibited = {"metadata", "generated_content", "ai_output", "provider_payload"}
    assert organization_fields.isdisjoint(prohibited)
    assert location_fields.isdisjoint(prohibited)
