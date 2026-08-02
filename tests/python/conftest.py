"""Shared Python test fixtures."""

from urllib.parse import urlsplit

import pytest

from apps.api.app.config import Settings


@pytest.fixture(scope="session")
def postgresql_test_url() -> str:
    """Return a guarded PostgreSQL-only integration-test URL."""
    database_url = Settings().integration_test_database_url()
    if database_url is None:
        pytest.skip("LILOS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database_name = urlsplit(database_url).path.removeprefix("/")
    if "test" not in database_name.lower():
        pytest.fail(
            "LILOS_TEST_DATABASE_URL must identify a database containing 'test' in its name"
        )
    return database_url
