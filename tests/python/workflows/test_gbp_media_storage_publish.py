"""Publishing an approved photo: an uploaded file is sent to Google by a 15-minute signed URL."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.authentication.models import UserProfile
from apps.api.app.execution import handlers as handler_mod
from apps.api.app.execution.handlers import _handle_gbp_upload_media
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.operations_models import GBPMedia
from apps.api.app.storage.objects import StorageNotConfiguredError

from .test_workflow_handlers import (
    _fake_token_resolver,
    clean_session_factory,
    enable_provider_writes_for_handler_contracts,
)

__all__ = ["clean_session_factory", "enable_provider_writes_for_handler_contracts"]


class RecordingAdapter:
    sent: list[dict[str, Any]] = []

    async def create_media(
        self, access_token: str, location_name: str, media_item: dict[str, Any]
    ) -> dict[str, Any]:
        type(self).sent.append(media_item)
        return {"name": f"{location_name}/media/m1"}

    async def get_media(self, access_token: str, media_name: str) -> dict[str, Any]:
        return {"name": media_name, "state": "VERIFIED"}


class SigningStorage:
    def __init__(self) -> None:
        self.signed: list[tuple[str, str, int]] = []

    async def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        raise AssertionError("publishing never writes to storage")

    async def delete(self, bucket: str, path: str) -> None:
        raise AssertionError("publishing never deletes from storage")

    async def signed_url(self, bucket: str, path: str, expires_in: int = 900) -> str:
        self.signed.append((bucket, path, expires_in))
        return f"https://storage.example.invalid/{bucket}/{path}?token=t"


async def seed_media(
    session: AsyncSession, *, source_reference: str | None, storage_path: str | None
) -> tuple[UUID, UUID, UUID]:
    org = Organization(
        name="Media Org",
        slug=f"media-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    profile = UserProfile(auth_user_id=uuid4(), status="active", version=1)
    session.add(profile)
    await session.flush()
    location = Location(
        organization_id=org.id,
        name="Downtown",
        slug=f"downtown-{uuid4().hex[:8]}",
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url="https://example.invalid",
        is_primary=True,
        version=1,
    )
    provider = Provider(
        key="google_business_profile",
        name="Google Business Profile",
        status="active",
        capabilities=["profile.read", "profile.write"],
    )
    session.add_all([location, provider])
    await session.flush()
    connection = IntegrationConnection(
        organization_id=org.id, provider_id=provider.id, status="connected"
    )
    session.add(connection)
    await session.flush()
    account = GBPAccount(
        organization_id=org.id,
        connection_id=connection.id,
        external_account_id="accounts/123",
        display_name="Example Business",
        status="discovered",
    )
    session.add(account)
    await session.flush()
    gbp_location = GBPLocation(
        organization_id=org.id,
        location_id=location.id,
        connection_id=connection.id,
        account_id=account.id,
        external_location_id="locations/456",
        business_name="Example Business - Downtown",
        mapping_status="confirmed",
        write_enabled=True,
        confirmed_by_user_id=profile.id,
        confirmed_at=datetime.now(UTC),
    )
    session.add(gbp_location)
    await session.flush()
    media = GBPMedia(
        organization_id=org.id,
        gbp_location_id=gbp_location.id,
        media_type="photo",
        source_reference=source_reference,
        storage_bucket="gbp-media" if storage_path else None,
        storage_path=storage_path,
        rights_authority="Owned by the business",
        idempotency_key=f"media-{uuid4().hex}",
        status="publishing",
    )
    session.add(media)
    await session.flush()
    return org.id, location.id, media.id


async def publish(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    storage: object,
    **media: str | None,
) -> tuple[Any, GBPMedia]:
    RecordingAdapter.sent = []
    monkeypatch.setattr(handler_mod, "_adapter_factory", RecordingAdapter)
    monkeypatch.setattr(handler_mod, "_token_resolver", _fake_token_resolver)
    monkeypatch.setattr(handler_mod, "_object_storage", lambda: storage)
    async with factory.begin() as session:
        org, location, media_id = await seed_media(
            session,
            source_reference=media.get("source_reference"),
            storage_path=media.get("storage_path"),
        )
    async with factory.begin() as session:
        outcome = await _handle_gbp_upload_media(
            session,
            organization_id=org,
            location_id=location,
            input_document={"media_id": str(media_id)},
            correlation_id="media-publish-test",
            workflow_run_id=uuid4(),
        )
    async with factory() as session:
        stored = await session.get(GBPMedia, media_id)
    assert stored is not None
    return outcome, stored


@pytest.mark.integration
@pytest.mark.anyio
async def test_uploaded_photo_is_sent_to_google_by_a_fifteen_minute_signed_url(
    clean_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = SigningStorage()
    outcome, media = await publish(
        clean_session_factory, monkeypatch, storage, storage_path="org/loc/photo.jpg"
    )
    assert outcome.result == "succeeded"
    assert storage.signed == [("gbp-media", "org/loc/photo.jpg", 900)]
    assert [item["sourceUrl"] for item in RecordingAdapter.sent] == [
        "https://storage.example.invalid/gbp-media/org/loc/photo.jpg?token=t"
    ]
    assert media.status == "verified"


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_photo_added_by_link_still_sends_its_own_address(
    clean_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = SigningStorage()
    outcome, media = await publish(
        clean_session_factory,
        monkeypatch,
        storage,
        source_reference="https://cdn.example.invalid/photo.jpg",
    )
    assert outcome.result == "succeeded"
    assert storage.signed == []
    assert RecordingAdapter.sent[0]["sourceUrl"] == "https://cdn.example.invalid/photo.jpg"
    assert media.status == "verified"


@pytest.mark.integration
@pytest.mark.anyio
async def test_storage_failure_fails_the_photo_with_a_typed_code_and_sends_nothing(
    clean_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    class Unconfigured(SigningStorage):
        async def signed_url(self, bucket: str, path: str, expires_in: int = 900) -> str:
            raise StorageNotConfiguredError

    outcome, media = await publish(
        clean_session_factory, monkeypatch, Unconfigured(), storage_path="org/loc/photo.jpg"
    )
    assert outcome.result == "retryable_failure"
    assert outcome.safe_error == "STORAGE_NOT_CONFIGURED"
    assert (media.status, media.safe_error_code) == ("failed", "STORAGE_NOT_CONFIGURED")
    assert RecordingAdapter.sent == []
