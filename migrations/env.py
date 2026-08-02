"""Alembic environment using the application's async PostgreSQL configuration."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.industries.models import Industry
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Organization.metadata
assert AuditEvent.metadata is target_metadata
assert Location.metadata is target_metadata
assert Industry.metadata is target_metadata


def configured_database_url() -> str:
    """Resolve a migration URL without exposing it in errors or logs."""
    database_url = Settings().alembic_database_url()
    if database_url is None:
        raise RuntimeError(
            "Database migrations require LILOS_MIGRATION_DATABASE_URL or LILOS_DATABASE_URL"
        )
    return database_url


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection."""
    context.configure(
        url=configured_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migration operations on a synchronous connection adapter."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create a short-lived async engine and execute migrations."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = configured_database_url().replace("%", "%%")
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"timeout": Settings().database_connect_timeout_seconds},
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations through SQLAlchemy's asyncpg dialect."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
