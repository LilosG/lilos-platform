"""Industry key, enum, and policy-document contract tests."""

from typing import cast

import pytest
from pydantic import ValidationError

from apps.api.app.industries.contracts import IndustryCreate
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.policy_documents import PolicyValue


def test_key_normalization_and_stable_statuses() -> None:
    command = IndustryCreate(key="  HOME_SERVICES  ", name="Home Services")
    assert command.key == "home_services"
    assert {item.value for item in IndustryStatus} == {"active", "deprecated", "archived"}


@pytest.mark.parametrize(
    "key", ["ab", "1restaurant", "home__services", "home_services_", "home-services", "få"]
)
def test_malformed_keys_are_rejected(key: str) -> None:
    with pytest.raises(ValidationError):
        IndustryCreate(key=key, name="Fabricated Industry")


def test_policy_documents_are_copied_and_allow_empty_objects() -> None:
    review: dict[str, PolicyValue] = {"approval": True}
    source: dict[str, PolicyValue] = {"review": review}
    command = IndustryCreate(
        key="fabricated_industry",
        name="Fabricated Industry",
        default_configuration=source,
    )
    review["approval"] = False
    assert command.default_configuration == {"review": {"approval": True}}
    assert command.default_risk_policy == {}


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"secret": "fabricated"},
        {"nested": {"client_secret": "fabricated"}},
        {"bad key": True},
        {"too_deep": {"a": {"b": {"c": {"d": {"e": True}}}}}},
        {"large": "x" * 17_000},
    ],
)
def test_invalid_or_secret_bearing_policy_documents_are_rejected(document: object) -> None:
    with pytest.raises(ValidationError):
        IndustryCreate(
            key="fabricated_industry",
            name="Fabricated Industry",
            default_configuration=cast(dict[str, PolicyValue], document),
        )
