"""Location-group contract normalization and bounds."""

import pytest
from pydantic import ValidationError

from apps.api.app.location_groups.contracts import LocationGroupCreate, LocationGroupReplace
from apps.api.app.location_groups.enums import LocationGroupStatus
from apps.api.app.location_groups.models import LocationGroup, LocationGroupMembership


def test_group_key_and_content_normalization() -> None:
    command = LocationGroupCreate(name="  North Region  ", key="  NORTH-REGION  ", description=" ")
    assert command.name == "North Region"
    assert command.key == "north-region"
    assert command.description is None


@pytest.mark.parametrize(
    "key",
    ["ab", "1north", "north--region", "north-", "north_region", "north!", "www"],
)
def test_invalid_or_reserved_keys_are_rejected(key: str) -> None:
    with pytest.raises(ValidationError):
        LocationGroupCreate(name="Group", key=key)


def test_name_description_and_extra_fields_are_bounded() -> None:
    with pytest.raises(ValidationError):
        LocationGroupCreate(name=" ", key="valid-key")
    with pytest.raises(ValidationError):
        LocationGroupCreate(name="x" * 121, key="valid-key")
    with pytest.raises(ValidationError):
        LocationGroupCreate(name="Group", key="valid-key", description="x" * 1_001)
    with pytest.raises(ValidationError):
        LocationGroupCreate.model_validate(
            {"name": "Group", "key": "valid-key", "metadata": {"not": "allowed"}}
        )


def test_replace_has_no_key_or_organization_mutation() -> None:
    assert set(LocationGroupReplace.model_fields) == {"name", "description", "expected_version"}
    assert [item.value for item in LocationGroupStatus] == ["active", "archived"]
    assert set(LocationGroup.__table__.columns.keys()) == {
        "id",
        "organization_id",
        "name",
        "key",
        "description",
        "status",
        "created_at",
        "updated_at",
        "archived_at",
        "version",
    }
    assert set(LocationGroupMembership.__table__.columns.keys()) == {
        "id",
        "organization_id",
        "location_group_id",
        "location_id",
        "created_at",
    }
