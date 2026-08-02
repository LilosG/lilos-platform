"""Organization contract and internal-route setting tests."""

import pytest
from pydantic import ValidationError

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.organizations.contracts import OrganizationCreate
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType


def valid_command(**overrides: object) -> OrganizationCreate:
    values: dict[str, object] = {
        "name": "Fabricated Example Organization",
        "slug": "fabricated-example",
        "organization_type": "test",
        "timezone": "America/Los_Angeles",
        "default_currency": "USD",
    }
    values.update(overrides)
    return OrganizationCreate.model_validate(values)


def test_slug_normalizes_only_whitespace_and_ascii_case() -> None:
    command = valid_command(slug="  FABRICATED-123  ")
    assert command.slug == "fabricated-123"


@pytest.mark.parametrize(
    "slug",
    [
        "ab",
        "admin",
        "api",
        "internal",
        "platform",
        "public",
        "system",
        "support",
        "www",
        "1fabricated",
        "fabricated--example",
        "fabricated-",
        "fabricated_example",
        "fabricated.example",
        "fåbricated",
    ],
)
def test_invalid_or_reserved_slugs_are_rejected(slug: str) -> None:
    with pytest.raises(ValidationError):
        valid_command(slug=slug)


@pytest.mark.parametrize("timezone", ["Not/A_Timezone", "UTC+7", ""])
def test_non_iana_timezones_are_rejected(timezone: str) -> None:
    with pytest.raises(ValidationError):
        valid_command(timezone=timezone)


@pytest.mark.parametrize("currency", ["usd", "US", "USDD", "12A"])
def test_currency_requires_three_uppercase_letters(currency: str) -> None:
    with pytest.raises(ValidationError):
        valid_command(default_currency=currency)


def test_stable_type_and_status_values() -> None:
    assert {item.value for item in OrganizationType} == {
        "client",
        "internal",
        "partner",
        "demo",
        "test",
    }
    assert {item.value for item in OrganizationStatus} == {
        "prospect",
        "onboarding",
        "active",
        "paused",
        "suspended",
        "offboarding",
        "archived",
    }


@pytest.mark.parametrize("environment", [EnvironmentName.LOCAL, EnvironmentName.TEST])
def test_internal_routes_may_be_explicitly_enabled_only_in_safe_environments(
    environment: EnvironmentName,
) -> None:
    settings = Settings(environment=environment, internal_admin_routes_enabled=True)
    assert settings.internal_admin_routes_enabled is True


@pytest.mark.parametrize(
    "environment",
    [EnvironmentName.DEVELOPMENT, EnvironmentName.STAGING, EnvironmentName.PRODUCTION],
)
def test_unsafe_internal_route_enablement_is_rejected(environment: EnvironmentName) -> None:
    with pytest.raises(ValidationError):
        Settings(environment=environment, internal_admin_routes_enabled=True)
