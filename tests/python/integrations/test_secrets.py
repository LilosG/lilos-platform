"""Deterministic tests for Fernet-backed secret storage. No real Google credentials."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.integrations.secrets import FernetSecretStore, SecretUnavailableError


def settings_with_key(*, key: str | None = None, version: int = 1) -> Settings:
    return Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "secret_encryption_key": key or Fernet.generate_key().decode("utf-8"),
            "secret_encryption_key_version": version,
        }
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_put_get_delete_round_trip(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        store = FernetSecretStore.create(session, settings_with_key())
        reference = await store.put("super-secret-value")
        assert await store.get(reference) == "super-secret-value"
        await store.delete(reference)
        with pytest.raises(SecretUnavailableError):
            await store.get(reference)


@pytest.mark.integration
@pytest.mark.anyio
async def test_create_without_configured_key_raises(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        settings = Settings.model_validate({"environment": EnvironmentName.TEST})
        with pytest.raises(SecretUnavailableError):
            FernetSecretStore.create(session, settings)


@pytest.mark.integration
@pytest.mark.anyio
async def test_get_with_malformed_reference_raises(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        store = FernetSecretStore.create(session, settings_with_key())
        with pytest.raises(SecretUnavailableError):
            await store.get("not-a-uuid")


@pytest.mark.integration
@pytest.mark.anyio
async def test_get_with_unknown_reference_raises(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        store = FernetSecretStore.create(session, settings_with_key())
        with pytest.raises(SecretUnavailableError):
            await store.get("00000000-0000-0000-0000-000000000000")


@pytest.mark.integration
@pytest.mark.anyio
async def test_ciphertext_is_not_the_plaintext(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        key = Fernet.generate_key().decode("utf-8")
        store = FernetSecretStore.create(session, settings_with_key(key=key))
        reference = await store.put("super-secret-value")
        row = await store._get_row(reference)  # noqa: SLF001 -- asserting the stored shape
        assert "super-secret-value" not in row.ciphertext
        assert row.key_version == 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_row_encrypted_under_a_different_version_cannot_be_read(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        key = Fernet.generate_key().decode("utf-8")
        writer = FernetSecretStore.create(session, settings_with_key(key=key, version=1))
        reference = await writer.put("super-secret-value")
        reader = FernetSecretStore.create(session, settings_with_key(key=key, version=2))
        with pytest.raises(SecretUnavailableError):
            await reader.get(reference)
