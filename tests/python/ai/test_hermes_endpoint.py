"""Canonical Hermes endpoint normalization and fail-closed consumer contracts."""

import pytest

from apps.api.app.agents.hermes_client import HermesRunsClient, HermesRuntimeError
from apps.api.app.ai.errors import AIProviderConfigurationError
from apps.api.app.ai.hermes import HermesAgentProvider
from apps.api.app.ai.hermes_endpoint import normalize_hermes_base_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("lilos-hermes:8642", "http://lilos-hermes:8642"),
        ("  lilos-hermes:8642/  ", "http://lilos-hermes:8642"),
        ("http://lilos-hermes:8642", "http://lilos-hermes:8642"),
        ("https://hermes.example.com/", "https://hermes.example.com"),
        ("HTTP://lilos-hermes:8642", "HTTP://lilos-hermes:8642"),
    ],
)
def test_normalize_hermes_base_url_accepts_private_hostport_and_http_origins(
    raw: str, expected: str
) -> None:
    assert normalize_hermes_base_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "ftp://hermes.example.com",
        "http://user:password@hermes.example.com",
        "http://hermes.example.com/private/path",
        "http://hermes.example.com?token=value",
        "http://hermes.example.com#fragment",
        "http://hermes.example.com:99999",
    ],
)
def test_normalize_hermes_base_url_rejects_unsafe_or_malformed_values(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_hermes_base_url(raw)


def test_runs_client_maps_invalid_endpoint_to_safe_configuration_error() -> None:
    with pytest.raises(HermesRuntimeError) as exc:
        HermesRunsClient("ftp://hermes.example.com", "test-hermes-key", timeout_seconds=5)

    assert exc.value.safe_code == "HERMES_CONFIGURATION_INVALID"


def test_completion_provider_maps_invalid_endpoint_to_configuration_error() -> None:
    with pytest.raises(AIProviderConfigurationError):
        HermesAgentProvider(
            api_key="test-hermes-key",
            base_url="http://user:password@hermes.example.com",
        )
