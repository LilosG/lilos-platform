"""Integration proof for the governed GBP Local Post publication boundary."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.app.authentication.models import UserProfile
from apps.api.app.execution.handlers import _handle_gbp_publish_post
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.operations_models import GBPPostPublication, GBPPostRevision
from apps.api.app.products.gbp.post_generation_models import GBPPostAsset

ROOT = Path(__file__).resolve().parents[3]
TARGET_URL = "https://example.com/electrical-panel-upgrades/"
POST_CONTENT = "Electrical panel upgrade planning for Carlsbad homeowners."
POST_RESOURCE = "accounts/123/locations/456/localPosts/contract-proof"


@pytest.fixture
async def clean_session_factory(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    monkeypatch.setenv("LILOS_PROVIDER_WRITES_ENABLED", "true")
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.downgrade, config, "20260801_0001")
    await asyncio.to_thread(command.upgrade, config, "head")
    engine = create_async_engine(postgresql_test_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _fake_token_resolver(
    session: AsyncSession, organization_id: UUID
) -> tuple[str, IntegrationConnection]:
    connection = await session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id
        )
    )
    assert connection is not None
    return "fake-access-token", connection


async def _seed_publication(
    session: AsyncSession,
    *,
    with_asset: bool,
) -> tuple[UUID, UUID, UUID]:
    org = Organization(
        name="GBP Publication Contract Test",
        slug=f"gbp-publication-contract-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()

    profile = UserProfile(auth_user_id=uuid4(), status="active", version=1)
    session.add(profile)
    await session.flush()

    location = Location(
        organization_id=org.id,
        name="Main Location",
        slug=f"main-{uuid4().hex[:8]}",
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url="https://example.com",
        is_primary=True,
        version=1,
    )
    provider = Provider(
        key=f"google_business_profile_{uuid4().hex[:8]}",
        name="Google Business Profile",
        status="active",
        capabilities=["profile.read", "profile.write"],
    )
    session.add_all([location, provider])
    await session.flush()

    connection = IntegrationConnection(
        organization_id=org.id,
        provider_id=provider.id,
        external_account_reference="accounts/123",
        status="connected",
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
        business_name="Example Business",
        mapping_status="confirmed",
        write_enabled=True,
        confirmed_by_user_id=profile.id,
        confirmed_at=datetime.now(UTC),
    )
    session.add(gbp_location)
    await session.flush()

    revision = GBPPostRevision(
        organization_id=org.id,
        gbp_location_id=gbp_location.id,
        post_key=uuid4(),
        revision=1,
        post_type="STANDARD",
        content=POST_CONTENT,
        call_to_action={"actionType": "LEARN_MORE", "url": TARGET_URL},
        publication_requirements={
            "version": 1,
            "cta_required": True,
            "media_required": True,
        },
        status="approved",
        created_at=datetime.now(UTC),
    )
    session.add(revision)
    await session.flush()

    if with_asset:
        session.add(
            GBPPostAsset(
                organization_id=org.id,
                post_revision_id=revision.id,
                source_type="google_drive",
                source_reference="drive:approved-image",
                provider_fetch_url="https://expired.example.invalid/image",
                metadata_document={
                    "file_id": "approved-image",
                    "name": "panel-upgrade.jpg",
                    "mime_type": "image/jpeg",
                    "path": "Example Business/work/panel-upgrade.jpg",
                },
                status="selected",
            )
        )
        await session.flush()

    definition = WorkflowDefinition(
        key="gbp.publish_post",
        name="Publish GBP post",
        owner="gbp",
        status="active",
    )
    session.add(definition)
    await session.flush()
    version = WorkflowVersion(
        definition_id=definition.id,
        version=1,
        status="approved",
        input_schema={},
        output_schema={},
        step_specification=[],
        retry_policy={},
        timeout_seconds=60,
    )
    session.add(version)
    await session.flush()
    run = WorkflowRun(
        organization_id=org.id,
        location_id=location.id,
        workflow_version_id=version.id,
        product_key="gbp",
        status="queued",
        trigger_type="api",
        idempotency_key=f"gbp-contract-run-{uuid4().hex}",
        request_hash="c" * 64,
        input_document={},
        correlation_id="gbp-publication-contract",
    )
    session.add(run)
    await session.flush()

    publication = GBPPostPublication(
        organization_id=org.id,
        post_revision_id=revision.id,
        workflow_run_id=run.id,
        idempotency_key=f"gbp-contract-publication-{uuid4().hex}",
        status="reserved",
    )
    session.add(publication)
    await session.flush()
    await session.commit()
    return org.id, location.id, publication.id


@pytest.mark.integration
@pytest.mark.anyio
async def test_governed_post_missing_media_never_dispatches_to_google(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from apps.api.app.execution import handlers as handler_mod

    create_calls = 0

    class NoWriteAdapter:
        async def create_local_post(
            self, access_token: str, location_name: str, post_body: dict[str, Any]
        ) -> dict[str, Any]:
            nonlocal create_calls
            create_calls += 1
            raise AssertionError("Google write must not occur without required media")

    original_factory = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = NoWriteAdapter  # type: ignore[assignment]
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory() as session:
            org_id, location_id, publication_id = await _seed_publication(
                session, with_asset=False
            )
            publication = await session.get(GBPPostPublication, publication_id)
            assert publication is not None
            outcome = await _handle_gbp_publish_post(
                session,
                organization_id=org_id,
                location_id=location_id,
                input_document={"publication_id": str(publication_id)},
                correlation_id="missing-media",
                workflow_run_id=publication.workflow_run_id,
            )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "POST_MEDIA_REQUIRED_MISSING"
        assert create_calls == 0
        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPostPublication, publication_id)
            assert refreshed is not None
            assert refreshed.status == "failed"
            assert refreshed.dispatched_at is None
            assert refreshed.provider_post_id is None
    finally:
        handler_mod._adapter_factory = original_factory
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_governed_post_verifies_exact_media_and_cta_delivery(
    clean_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api.app.execution import handlers as handler_mod

    create_calls = 0
    published_body: dict[str, Any] = {}

    class MatchingAdapter:
        async def create_local_post(
            self, access_token: str, location_name: str, post_body: dict[str, Any]
        ) -> dict[str, Any]:
            nonlocal create_calls
            create_calls += 1
            published_body.update(post_body)
            return {"name": POST_RESOURCE, "state": "LIVE"}

        async def get_local_post(self, access_token: str, post_name: str) -> dict[str, Any]:
            return {
                "name": post_name,
                "state": "LIVE",
                "topicType": "STANDARD",
                "summary": POST_CONTENT,
                "callToAction": {"actionType": "LEARN_MORE", "url": TARGET_URL},
                "media": [{"mediaFormat": "PHOTO", "googleUrl": "https://google/photo"}],
            }

    original_factory = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = MatchingAdapter  # type: ignore[assignment]
    handler_mod._token_resolver = _fake_token_resolver
    monkeypatch.setattr(
        "apps.api.app.products.gbp.post_publish_handler.GoogleDriveMediaService.public_proxy_url",
        lambda *args, **kwargs: "https://api.example.invalid/provider-media/image-token",
    )
    try:
        async with clean_session_factory() as session:
            org_id, location_id, publication_id = await _seed_publication(
                session, with_asset=True
            )
            publication = await session.get(GBPPostPublication, publication_id)
            assert publication is not None
            outcome = await _handle_gbp_publish_post(
                session,
                organization_id=org_id,
                location_id=location_id,
                input_document={"publication_id": str(publication_id)},
                correlation_id="matching-provider-payload",
                workflow_run_id=publication.workflow_run_id,
            )

        assert outcome.result == "succeeded"
        assert create_calls == 1
        assert published_body["callToAction"] == {
            "actionType": "LEARN_MORE",
            "url": TARGET_URL,
        }
        assert published_body["media"] == [
            {
                "mediaFormat": "PHOTO",
                "sourceUrl": "https://api.example.invalid/provider-media/image-token",
            }
        ]
        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPostPublication, publication_id)
            assert refreshed is not None
            assert refreshed.status == "verified"
            assert refreshed.provider_post_id == POST_RESOURCE
            assert refreshed.verified_at is not None
    finally:
        handler_mod._adapter_factory = original_factory
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_live_post_missing_media_reconciles_without_duplicate_create(
    clean_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api.app.execution import handlers as handler_mod

    create_calls = 0
    read_calls = 0

    class MissingMediaAdapter:
        async def create_local_post(
            self, access_token: str, location_name: str, post_body: dict[str, Any]
        ) -> dict[str, Any]:
            nonlocal create_calls
            create_calls += 1
            return {"name": POST_RESOURCE, "state": "LIVE"}

        async def get_local_post(self, access_token: str, post_name: str) -> dict[str, Any]:
            nonlocal read_calls
            read_calls += 1
            return {
                "name": post_name,
                "state": "LIVE",
                "topicType": "STANDARD",
                "summary": POST_CONTENT,
                "callToAction": {"actionType": "LEARN_MORE", "url": TARGET_URL},
                "media": [],
            }

    original_factory = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = MissingMediaAdapter  # type: ignore[assignment]
    handler_mod._token_resolver = _fake_token_resolver
    monkeypatch.setattr(
        "apps.api.app.products.gbp.post_publish_handler.GoogleDriveMediaService.public_proxy_url",
        lambda *args, **kwargs: "https://api.example.invalid/provider-media/image-token",
    )
    try:
        async with clean_session_factory() as session:
            org_id, location_id, publication_id = await _seed_publication(
                session, with_asset=True
            )
            publication = await session.get(GBPPostPublication, publication_id)
            assert publication is not None
            workflow_run_id = publication.workflow_run_id
            first = await _handle_gbp_publish_post(
                session,
                organization_id=org_id,
                location_id=location_id,
                input_document={"publication_id": str(publication_id)},
                correlation_id="missing-provider-media-first",
                workflow_run_id=workflow_run_id,
            )
            second = await _handle_gbp_publish_post(
                session,
                organization_id=org_id,
                location_id=location_id,
                input_document={"publication_id": str(publication_id)},
                correlation_id="missing-provider-media-second",
                workflow_run_id=workflow_run_id,
            )

        assert first.result == "ambiguous"
        assert first.safe_error == "POST_MEDIA_MISSING"
        assert second.result == "ambiguous"
        assert second.safe_error == "POST_MEDIA_MISSING"
        assert create_calls == 1
        assert read_calls == 2
        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPostPublication, publication_id)
            assert refreshed is not None
            assert refreshed.status == "reconciliation_required"
            assert refreshed.safe_error_code == "POST_MEDIA_MISSING"
            assert refreshed.provider_post_id == POST_RESOURCE
            assert refreshed.dispatched_at is not None
    finally:
        handler_mod._adapter_factory = original_factory
        handler_mod._token_resolver = original_resolver
