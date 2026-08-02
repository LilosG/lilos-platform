"""Location command validation tests."""

import pytest
from pydantic import ValidationError

from apps.api.app.locations.contracts import LocationCreate


def payload(location_type: str = "physical") -> dict[str, object]:
    base: dict[str, object] = {
        "name": "Fabricated Location",
        "slug": "  FABRICATED-ONE  ",
        "location_type": location_type,
        "timezone": "UTC",
        "country_code": "US",
    }
    if location_type in {"physical", "hybrid"}:
        base.update(
            address_line_1="1 Example Way", city="Example", region="CA", postal_code="00000"
        )
    if location_type in {"service_area", "hybrid"}:
        base["service_area_description"] = "Fabricated service boundary"
    if location_type == "virtual":
        base["website_url"] = "https://example.invalid"
    return base


@pytest.mark.parametrize("location_type", ["physical", "service_area", "hybrid", "virtual"])
def test_supported_types_and_slug_normalization(location_type: str) -> None:
    command = LocationCreate.model_validate(payload(location_type))
    assert command.slug == "fabricated-one"


@pytest.mark.parametrize("slug", ["admin", "a--b", "1bad", "bad_thing"])
def test_rejects_reserved_or_malformed_slugs(slug: str) -> None:
    data = payload()
    data["slug"] = slug
    with pytest.raises(ValidationError):
        LocationCreate.model_validate(data)


def test_rejects_invalid_type_specific_combinations() -> None:
    for data in [
        {**payload("physical"), "city": None},
        {**payload("service_area"), "address_line_1": "1 Example Way"},
        {**payload("virtual"), "latitude": 1},
    ]:
        with pytest.raises(ValidationError):
            LocationCreate.model_validate(data)
