"""Canonical Google Business Profile resource-name regression tests.

Covers the central provider-contract correction: Business Information v1
uses ``locations/{locationId}`` (NOT account-qualified) for get/patch, while
legacy My Business v4 (reviews, localPosts) requires the account-qualified
``accounts/{accountId}/locations/{locationId}`` parent — both constructed
from the same canonical location identity.
"""

from __future__ import annotations

import pytest

from apps.api.app.products.gbp.resource_names import (
    location_id_from_name,
    normalize_location_name,
    v1_location_name,
    v4_localposts_parent,
    v4_location_parent,
    v4_review_name,
)


class TestNormalizeLocationName:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("locations/123", "locations/123"),
            ("accounts/456/locations/123", "locations/123"),
            ("123", "locations/123"),
            ("locations/ accounts/456/locations/789", "locations/789"),
        ],
    )
    def test_canonical_forms(self, raw: str, expected: str) -> None:
        assert normalize_location_name(raw) == expected

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            normalize_location_name("")

    def test_bare_id_extracted(self) -> None:
        assert location_id_from_name("accounts/456/locations/789") == "789"
        assert location_id_from_name("locations/789") == "789"


class TestV1ResourceName:
    def test_v1_get_patch_uses_locations_only(self) -> None:
        # Business Information v1 locations.get / locations.patch use the
        # canonical locations/{locationId} — NOT accounts/.../locations/...
        assert v1_location_name("locations/123") == "locations/123"
        assert "accounts/" not in v1_location_name("accounts/456/locations/123")

    def test_v1_name_never_account_qualified(self) -> None:
        name = v1_location_name("123")
        assert name == "locations/123"
        assert not name.startswith("accounts/")


class TestV4ResourceName:
    def test_v4_location_parent_account_qualified(self) -> None:
        # Legacy My Business v4 reviews/localPosts require the
        # account-qualified parent.
        assert v4_location_parent("456", "locations/123") == "accounts/456/locations/123"

    def test_v4_accepts_prefixed_account_id(self) -> None:
        # Existing rows may store the account id with the accounts/ prefix.
        assert v4_location_parent("accounts/456", "locations/123") == "accounts/456/locations/123"

    def test_v4_review_name(self) -> None:
        assert (
            v4_review_name("456", "locations/123", "rev-abc")
            == "accounts/456/locations/123/reviews/rev-abc"
        )

    def test_v4_localposts_parent(self) -> None:
        assert v4_localposts_parent("456", "locations/123") == "accounts/456/locations/123"

    def test_v4_and_v1_share_canonical_identity(self) -> None:
        # The same canonical external_location_id feeds both surfaces without
        # mixing conventions.
        canonical = "locations/123"
        assert v1_location_name(canonical) == "locations/123"
        assert v4_location_parent("456", canonical) == "accounts/456/locations/123"
