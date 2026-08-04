"""Integration tests for the read-only runtime heartbeat verification script."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.observability.models import ServiceHeartbeat
from scripts import verify_runtime_heartbeats as verify_module

ENVIRONMENT = "production"


async def _insert_heartbeat(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    service: str,
    instance_key: str,
    release: str = "test-release",
    status: str = "running",
    last_seen_at: datetime | None = None,
    environment: str = ENVIRONMENT,
) -> None:
    async with session_factory.begin() as session:
        session.add(
            ServiceHeartbeat(
                environment=environment,
                service=service,
                instance_key=instance_key,
                release=release,
                status=status,
                last_seen_at=last_seen_at or datetime.now(UTC),
                safe_details={"process": "durable-postgresql"},
            )
        )


@pytest.mark.integration
def test_fresh_single_heartbeats_pass(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    observability_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.setenv("HEARTBEAT_ENVIRONMENT", ENVIRONMENT)

    async def scenario() -> int:
        await _insert_heartbeat(
            observability_session_factory, service="lilos-worker", instance_key="worker-a"
        )
        await _insert_heartbeat(
            observability_session_factory, service="lilos-scheduler", instance_key="scheduler-a"
        )
        return await verify_module.verify()

    assert asyncio.run(scenario()) == 0


@pytest.mark.integration
def test_missing_heartbeat_fails(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    observability_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.setenv("HEARTBEAT_ENVIRONMENT", ENVIRONMENT)

    async def scenario() -> int:
        await _insert_heartbeat(
            observability_session_factory, service="lilos-worker", instance_key="worker-a"
        )
        # No scheduler heartbeat inserted at all.
        return await verify_module.verify()

    assert asyncio.run(scenario()) == 1


@pytest.mark.integration
def test_stale_heartbeat_fails(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    observability_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.setenv("HEARTBEAT_ENVIRONMENT", ENVIRONMENT)
    monkeypatch.setenv("HEARTBEAT_MAX_AGE_SECONDS", "60")

    async def scenario() -> int:
        stale = datetime.now(UTC) - timedelta(seconds=600)
        await _insert_heartbeat(
            observability_session_factory,
            service="lilos-worker",
            instance_key="worker-a",
            last_seen_at=stale,
        )
        await _insert_heartbeat(
            observability_session_factory, service="lilos-scheduler", instance_key="scheduler-a"
        )
        return await verify_module.verify()

    assert asyncio.run(scenario()) == 1


@pytest.mark.integration
def test_duplicate_active_identity_fails(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    observability_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.setenv("HEARTBEAT_ENVIRONMENT", ENVIRONMENT)

    async def scenario() -> int:
        await _insert_heartbeat(
            observability_session_factory, service="lilos-worker", instance_key="worker-a"
        )
        await _insert_heartbeat(
            observability_session_factory, service="lilos-worker", instance_key="worker-b"
        )
        await _insert_heartbeat(
            observability_session_factory, service="lilos-scheduler", instance_key="scheduler-a"
        )
        return await verify_module.verify()

    assert asyncio.run(scenario()) == 1


@pytest.mark.integration
def test_unexpected_status_fails(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    observability_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.setenv("HEARTBEAT_ENVIRONMENT", ENVIRONMENT)

    async def scenario() -> int:
        await _insert_heartbeat(
            observability_session_factory,
            service="lilos-worker",
            instance_key="worker-a",
            status="stopping",
        )
        await _insert_heartbeat(
            observability_session_factory, service="lilos-scheduler", instance_key="scheduler-a"
        )
        return await verify_module.verify()

    assert asyncio.run(scenario()) == 1


@pytest.mark.integration
def test_release_mismatch_fails_when_expected_release_set(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    observability_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.setenv("HEARTBEAT_ENVIRONMENT", ENVIRONMENT)
    monkeypatch.setenv("HEARTBEAT_EXPECTED_RELEASE", "expected-commit-sha")

    async def scenario() -> int:
        await _insert_heartbeat(
            observability_session_factory,
            service="lilos-worker",
            instance_key="worker-a",
            release="other-commit-sha",
        )
        await _insert_heartbeat(
            observability_session_factory,
            service="lilos-scheduler",
            instance_key="scheduler-a",
            release="expected-commit-sha",
        )
        return await verify_module.verify()

    assert asyncio.run(scenario()) == 1


@pytest.mark.integration
def test_wrong_environment_is_not_counted(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    observability_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.setenv("HEARTBEAT_ENVIRONMENT", ENVIRONMENT)

    async def scenario() -> int:
        # A fresh heartbeat in a different environment must not satisfy production.
        await _insert_heartbeat(
            observability_session_factory,
            service="lilos-worker",
            instance_key="worker-a",
            environment="staging",
        )
        await _insert_heartbeat(
            observability_session_factory, service="lilos-scheduler", instance_key="scheduler-a"
        )
        return await verify_module.verify()

    assert asyncio.run(scenario()) == 1


@pytest.mark.integration
def test_invalid_max_age_blocks(postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.setenv("HEARTBEAT_MAX_AGE_SECONDS", "not-a-number")

    with pytest.raises(SystemExit, match="HEARTBEAT_MAX_AGE_SECONDS must be numeric"):
        asyncio.run(verify_module.verify())
