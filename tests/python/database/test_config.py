from pydantic import PostgresDsn, TypeAdapter

from apps.api.app.config import EnvironmentName, Settings

POSTGRES_DSN_ADAPTER = TypeAdapter(PostgresDsn)


def test_database_urls_are_optional_for_application_startup() -> None:
    settings = Settings(
        environment=EnvironmentName.TEST,
        migration_database_url=None,
        test_database_url=None,
    )

    assert settings.application_database_url() is None
    assert settings.alembic_database_url() is None
    assert settings.database_connect_timeout_seconds == 5.0


def test_plain_postgresql_url_is_normalized_for_asyncpg() -> None:
    settings = Settings(
        environment=EnvironmentName.TEST,
        database_url=POSTGRES_DSN_ADAPTER.validate_python(
            "postgresql://user:password@localhost/lilos_test"
        ),
        migration_database_url=None,
    )

    assert (
        settings.application_database_url()
        == "postgresql+asyncpg://user:password@localhost/lilos_test"
    )
    assert settings.alembic_database_url() == settings.application_database_url()


def test_migration_database_url_can_be_separate() -> None:
    settings = Settings(
        environment=EnvironmentName.STAGING,
        database_url=POSTGRES_DSN_ADAPTER.validate_python(
            "postgresql+asyncpg://app:password@db.example/lilos"
        ),
        migration_database_url=POSTGRES_DSN_ADAPTER.validate_python(
            "postgresql+asyncpg://migrator:password@db.example/lilos"
        ),
    )

    application_url = settings.application_database_url()
    migration_url = settings.alembic_database_url()
    assert application_url is not None
    assert migration_url is not None
    assert "app:" in application_url
    assert "migrator:" in migration_url
