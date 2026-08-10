"""Focused tests for workflow step-handler invocation and behavior.

These tests prove that registered handlers are actually invoked by the
runtime (the guard on ``step_specification`` was previously always false
because ``_resolve_workflow_version`` creates versions with
``step_specification=[]``), and that handlers do not fabricate ``verified``
publication status without a real provider write.
"""

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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.app.authentication.models import UserProfile
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.handlers import (
    _handle_content_publish,
    _handle_gbp_publish_change,
    _handle_gbp_publish_post,
    _handle_reviews_publish_response,
    get_workflow_handler,
    register_workflow_handler,
    registered_workflow_keys,
)
from apps.api.app.execution.models import (
    Job,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.execution.runtime import _execute_workflow_job
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import (
    GBPAccount,
    GBPLocation,
    GBPProfileChangeRevision,
    GBPProfileSnapshot,
    GBPPublication,
)
from apps.api.app.products.gbp.operations_models import (
    GBPPostPublication,
    GBPPostRevision,
)

ROOT = Path(__file__).resolve().parents[3]


async def _fake_token_resolver(session: AsyncSession, organization_id: UUID) -> tuple[str, object]:
    """Bypass real OAuth/secret-store; return a dummy token and connection."""
    from sqlalchemy import select

    from apps.api.app.integrations.models import IntegrationConnection

    connection = await session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id,
        )
    )
    if connection is None:
        raise RuntimeError("no connection")
    return "fake-access-token", connection


@pytest.fixture
async def clean_session_factory(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Run migrations from scratch and yield a session factory on a clean database."""
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


# ---------------------------------------------------------------------------
# Registry tests (no database needed)
# ---------------------------------------------------------------------------


def test_all_catalog_workflow_keys_have_registered_handlers() -> None:
    """Every catalog workflow key must have a registered handler."""
    from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES

    registered = set(registered_workflow_keys())
    for key in WORKFLOW_TYPES:
        assert key in registered, f"no handler registered for catalog key {key}"
        assert get_workflow_handler(key) is not None


def test_unknown_workflow_key_has_no_handler() -> None:
    assert get_workflow_handler("nonexistent.workflow") is None


# ---------------------------------------------------------------------------
# Runtime handler-invocation guard test (proves handlers are actually called)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.anyio
async def test_runtime_invokes_registered_handler_for_catalog_key(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The runtime must invoke the registered handler for a catalog workflow key.

    Regression: the previous guard ``if version.step_specification and
    workflow_key:`` short-circuited because ``step_specification`` was always
    ``[]``, so handlers were never invoked and every workflow silently
    completed without doing any real work.
    """
    invoked: dict[str, object] = {}

    async def fake_handler(
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        input_document: dict[str, object],
        correlation_id: str,
    ) -> JobOutcome:
        invoked["called"] = True
        invoked["input"] = input_document
        return JobOutcome(result="succeeded", result_reference="fake-handler-result")

    test_key = f"test.catalog_key.{uuid4().hex[:8]}"
    register_workflow_handler(test_key, fake_handler)
    from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES

    WORKFLOW_TYPES[test_key] = ("Test", "test")
    try:
        async with clean_session_factory.begin() as session:
            org = Organization(
                name="Handler Invocation Test",
                slug=f"handler-invocation-test-{uuid4().hex[:8]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(org)
            await session.flush()

            definition = WorkflowDefinition(
                key=test_key, name="Test", owner="test", status="active"
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
                timeout_seconds=30,
            )
            session.add(version)
            await session.flush()
            run = WorkflowRun(
                organization_id=org.id,
                workflow_version_id=version.id,
                product_key="test",
                status="queued",
                trigger_type="api",
                idempotency_key="handler-test-key-001",
                request_hash="a" * 64,
                input_document={"hello": "world"},
                correlation_id="handler-test",
            )
            session.add(run)
            await session.flush()
            job = Job(
                organization_id=org.id,
                workflow_run_id=run.id,
                job_type="workflow.execute",
                status="queued",
                idempotency_key="handler-job-key-001",
                payload={"run_id": str(run.id)},
            )
            session.add(job)
            await session.flush()
            run_id = run.id

            outcome = await _execute_workflow_job(session, job)

        assert invoked.get("called") is True
        assert invoked.get("input") == {"hello": "world"}
        assert outcome.result == "succeeded"
        assert outcome.result_reference == "fake-handler-result"

        async with clean_session_factory() as session:
            refreshed = await session.get(WorkflowRun, run_id)
            assert refreshed is not None
            assert refreshed.status == "completed"
            assert refreshed.output_reference == "fake-handler-result"
    finally:
        del WORKFLOW_TYPES[test_key]


@pytest.mark.integration
@pytest.mark.anyio
async def test_runtime_fails_closed_for_catalog_key_with_no_handler(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A catalog key with no registered handler must fail closed, not silently complete."""
    from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES

    test_key = f"test.no_handler.{uuid4().hex[:8]}"
    WORKFLOW_TYPES[test_key] = ("No Handler", "test")
    try:
        async with clean_session_factory.begin() as session:
            org = Organization(
                name="No Handler Test",
                slug=f"no-handler-test-{uuid4().hex[:8]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(org)
            await session.flush()

            definition = WorkflowDefinition(
                key=test_key, name="No Handler", owner="test", status="active"
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
                timeout_seconds=30,
            )
            session.add(version)
            await session.flush()
            run = WorkflowRun(
                organization_id=org.id,
                workflow_version_id=version.id,
                product_key="test",
                status="queued",
                trigger_type="api",
                idempotency_key="no-handler-test-key-001",
                request_hash="b" * 64,
                input_document={},
                correlation_id="no-handler-test",
            )
            session.add(run)
            await session.flush()
            job = Job(
                organization_id=org.id,
                workflow_run_id=run.id,
                job_type="workflow.execute",
                status="queued",
                idempotency_key="no-handler-job-key-001",
                payload={"run_id": str(run.id)},
            )
            session.add(job)
            await session.flush()
            run_id = run.id

            outcome = await _execute_workflow_job(session, job)

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "WORKFLOW_HANDLER_NOT_REGISTERED"

        async with clean_session_factory() as session:
            refreshed = await session.get(WorkflowRun, run_id)
            assert refreshed is not None
            assert refreshed.status == "failed"
            assert refreshed.failure_code == "WORKFLOW_HANDLER_NOT_REGISTERED"
    finally:
        del WORKFLOW_TYPES[test_key]


# ---------------------------------------------------------------------------
# GBP profile-change handler
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_publish_change_resolves_provider_location_from_revision(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A publication's platform location UUID is never a GBP location UUID."""
    from apps.api.app.execution import handlers as handler_mod

    patched: dict[str, object] = {}

    class FakeProfileAdapter:
        async def patch_location(
            self,
            access_token: str,
            location_name: str,
            fields: dict[str, Any],
            update_mask: list[str],
            idempotency_key: str,
        ) -> dict[str, Any]:
            patched.update(
                {
                    "access_token": access_token,
                    "location_name": location_name,
                    "fields": fields,
                    "update_mask": update_mask,
                    "idempotency_key": idempotency_key,
                }
            )
            return {"name": location_name, "profile": {"description": "Updated"}}

        async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
            return {"name": location_name, "profile": {"description": "Updated"}}

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = FakeProfileAdapter  # type: ignore[assignment]
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            org = Organization(
                name="GBP Profile Handler Test",
                slug=f"gbp-profile-handler-{uuid4().hex[:8]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(org)
            await session.flush()
            location = Location(
                organization_id=org.id,
                name="GBP Profile Handler Location",
                slug=f"gbp-profile-handler-location-{uuid4().hex[:8]}",
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
                display_name="Profile Handler Account",
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
                business_name="Profile Handler Location",
                mapping_status="confirmed",
                write_enabled=True,
            )
            session.add(gbp_location)
            await session.flush()
            snapshot = GBPProfileSnapshot(
                organization_id=org.id,
                gbp_location_id=gbp_location.id,
                normalized_profile={"profile": {"description": "Original"}},
                content_hash="a" * 64,
                completeness="full",
                observed_at=datetime.now(UTC),
            )
            definition = WorkflowDefinition(
                key="gbp.publish_change",
                name="Publish GBP profile change",
                owner="gbp",
                status="active",
            )
            session.add_all([snapshot, definition])
            await session.flush()
            version = WorkflowVersion(
                definition_id=definition.id,
                version=1,
                status="approved",
                input_schema={},
                output_schema={},
                step_specification=[],
                retry_policy={},
                timeout_seconds=30,
            )
            session.add(version)
            await session.flush()
            run = WorkflowRun(
                organization_id=org.id,
                location_id=location.id,
                workflow_version_id=version.id,
                product_key="gbp",
                status="running",
                trigger_type="api",
                idempotency_key="gbp-profile-handler-run",
                request_hash="c" * 64,
                input_document={},
                correlation_id="gbp-profile-handler",
            )
            session.add(run)
            await session.flush()
            revision = GBPProfileChangeRevision(
                organization_id=org.id,
                location_id=location.id,
                gbp_location_id=gbp_location.id,
                change_identity=uuid4(),
                revision_number=1,
                base_snapshot_id=snapshot.id,
                desired_fields={"profile.description": "Updated"},
                diff_document={},
                fact_revision_ids=[],
                status="approved",
                risk_level="low",
                content_hash="b" * 64,
            )
            session.add(revision)
            await session.flush()
            publication = GBPPublication(
                organization_id=org.id,
                location_id=location.id,
                change_revision_id=revision.id,
                workflow_run_id=run.id,
                idempotency_key="gbp-profile-handler-publication",
                status="reserved",
                update_mask=["profile.description"],
            )
            session.add(publication)
            await session.flush()
            publication_id = publication.id
            organization_id = org.id

            assert location.id != gbp_location.id
            outcome = await _handle_gbp_publish_change(
                session,
                organization_id=organization_id,
                location_id=location.id,
                input_document={"publication_id": str(publication_id)},
                correlation_id="gbp-profile-handler",
            )

        assert outcome.result == "succeeded"
        assert patched["location_name"] == "locations/456"
        assert patched["fields"] == {"profile.description": "Updated"}
        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPublication, publication_id)
            assert refreshed is not None
            assert refreshed.status == "verified"
            assert refreshed.safe_error_code is None
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


# ---------------------------------------------------------------------------
# GBP post handler: must NOT fabricate "verified" status
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_publish_post_creates_local_post_and_verifies(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The GBP post handler creates a Local Post via the adapter and verifies."""
    from apps.api.app.execution import handlers as handler_mod

    post_resource_name = "accounts/123/locations/456/localPosts/abc123"

    class FakePostAdapter:
        async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def list_locations(
            self, access_token: str, account_name: str
        ) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
            raise NotImplementedError

        async def patch_location(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def update_review_reply(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def get_review(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def list_reviews(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def create_local_post(
            self, access_token: str, location_name: str, post_body: dict[str, Any]
        ) -> dict[str, Any]:
            return {"name": post_resource_name, "state": "LIVE", "postType": "STANDARD"}

        async def get_local_post(self, access_token: str, post_name: str) -> dict[str, Any]:
            return {"name": post_name, "state": "LIVE", "postType": "STANDARD"}

        async def list_local_posts(
            self, access_token: str, location_name: str
        ) -> list[dict[str, Any]]:
            return [{"name": post_resource_name, "state": "LIVE"}]

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = FakePostAdapter
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            org = Organization(
                name="GBP Post Handler Test",
                slug=f"gbp-post-handler-test-{uuid4().hex[:8]}",
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
                name="Downtown",
                slug="downtown",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=True,
                version=1,
            )
            session.add(location)
            await session.flush()

            provider = Provider(
                key="google_business_profile",
                name="Google Business Profile",
                status="active",
                capabilities=["profile.read", "profile.write"],
            )
            session.add(provider)
            await session.flush()
            connection = IntegrationConnection(
                organization_id=org.id,
                provider_id=provider.id,
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
                business_name="Example Business - Downtown",
                mapping_status="confirmed",
                write_enabled=True,
                confirmed_by_user_id=profile.id,
                confirmed_at=datetime.now(UTC),
            )
            session.add(gbp_location)
            await session.flush()

            post_revision = GBPPostRevision(
                organization_id=org.id,
                gbp_location_id=gbp_location.id,
                post_key=uuid4(),
                revision=1,
                post_type="STANDARD",
                content="Test post content",
                status="approved",
                created_at=datetime.now(UTC),
            )
            session.add(post_revision)
            await session.flush()

            workflow_definition = WorkflowDefinition(
                key="gbp.publish_post", name="Publish GBP post", owner="gbp", status="active"
            )
            session.add(workflow_definition)
            await session.flush()
            workflow_version = WorkflowVersion(
                definition_id=workflow_definition.id,
                version=1,
                status="approved",
                input_schema={},
                output_schema={},
                step_specification=[],
                retry_policy={},
                timeout_seconds=60,
            )
            session.add(workflow_version)
            await session.flush()
            workflow_run = WorkflowRun(
                organization_id=org.id,
                location_id=location.id,
                workflow_version_id=workflow_version.id,
                product_key="gbp",
                status="queued",
                trigger_type="api",
                idempotency_key="gbp-post-handler-test-run-001",
                request_hash="c" * 64,
                input_document={},
                correlation_id="gbp-post-handler-test",
            )
            session.add(workflow_run)
            await session.flush()

            post_pub = GBPPostPublication(
                organization_id=org.id,
                post_revision_id=post_revision.id,
                workflow_run_id=workflow_run.id,
                idempotency_key="gbp-post-handler-test-pub-001",
                status="reserved",
            )
            session.add(post_pub)
            await session.flush()
            post_pub_id = post_pub.id

            outcome = await _handle_gbp_publish_post(
                session,
                organization_id=org.id,
                location_id=location.id,
                input_document={"publication_id": str(post_pub_id)},
                correlation_id="test",
            )

        assert outcome.result == "succeeded"
        assert outcome.result_reference == f"publication:{post_pub_id}"

        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPostPublication, post_pub_id)
            assert refreshed is not None
            assert refreshed.status == "verified"
            assert refreshed.provider_post_id == post_resource_name
            assert refreshed.verified_at is not None
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


# ---------------------------------------------------------------------------
# Content publish handler: must NOT fabricate "verified" status
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.anyio
async def test_content_publish_fails_closed_for_missing_publication(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The content handler must return permanent_failure when no publication exists."""
    async with clean_session_factory.begin() as session:
        org = Organization(
            name="Content Handler Test",
            slug=f"content-handler-test-{uuid4().hex[:8]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        outcome = await _handle_content_publish(
            session,
            organization_id=org.id,
            location_id=None,
            input_document={"publication_id": str(uuid4())},
            correlation_id="test",
        )

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "PUBLICATION_NOT_FOUND"


@pytest.mark.anyio
async def test_content_publish_requires_publication_id() -> None:
    outcome = await _handle_content_publish(
        None,  # type: ignore[arg-type]
        organization_id=uuid4(),
        location_id=None,
        input_document={},
        correlation_id="test",
    )
    assert outcome.result == "permanent_failure"


# ---------------------------------------------------------------------------
# Reviews publish-response handler: real provider-backed publication
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_publishes_and_verifies(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The review-response handler publishes via the adapter and verifies."""
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.integrations.models import Provider, ProviderResourceMapping
    from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
    from apps.api.app.products.reviews.models import (
        Review,
        ReviewResponseRevision,
        ReviewRevision,
    )

    approved_comment = "Thank you for your kind words!"

    class FakeReviewAdapter:
        async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def list_locations(
            self, access_token: str, account_name: str
        ) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
            raise NotImplementedError

        async def patch_location(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def update_review_reply(
            self, access_token: str, review_name: str, comment: str
        ) -> dict[str, Any]:
            assert comment == approved_comment
            return {"comment": comment}

        async def get_review(self, access_token: str, review_name: str) -> dict[str, Any]:
            return {"reviewReply": {"comment": approved_comment}}

        async def list_reviews(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def create_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def get_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def list_local_posts(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = FakeReviewAdapter
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            org = Organization(
                name="Reviews Handler Test",
                slug=f"reviews-handler-test-{uuid4().hex[:8]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(org)
            await session.flush()

            location = Location(
                organization_id=org.id,
                name="Reviews Handler Loc",
                slug=f"reviews-handler-loc-{uuid4().hex[:8]}",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=True,
                version=1,
            )
            session.add(location)
            await session.flush()

            provider = Provider(
                key="google_business_profile",
                name="Google Business Profile",
                status="active",
                capabilities=["reviews.read"],
            )
            session.add(provider)
            await session.flush()

            connection = IntegrationConnection(
                organization_id=org.id,
                provider_id=provider.id,
                external_account_reference="accounts/rev-test",
                status="connected",
            )
            session.add(connection)
            await session.flush()

            account = GBPAccount(
                organization_id=org.id,
                connection_id=connection.id,
                external_account_id="accounts/rev-test",
                display_name="Review Test Account",
                status="discovered",
            )
            session.add(account)
            await session.flush()

            resource_mapping = ProviderResourceMapping(
                organization_id=org.id,
                connection_id=connection.id,
                resource_type="gbp_location",
                external_resource_id="locations/rev-loc",
                platform_resource_id=location.id,
                status="active",
            )
            session.add(resource_mapping)
            await session.flush()

            gbp_location = GBPLocation(
                organization_id=org.id,
                location_id=location.id,
                connection_id=connection.id,
                account_id=account.id,
                integration_resource_id=resource_mapping.id,
                external_location_id="locations/rev-loc",
                business_name="Review Test Location",
                mapping_status="confirmed",
                write_enabled=True,
            )
            session.add(gbp_location)
            await session.flush()

            review = Review(
                organization_id=org.id,
                location_id=location.id,
                integration_resource_id=resource_mapping.id,
                external_review_id="review-123",
                provider="google",
                rating=5,
                status="triaged",
                review_created_at=datetime.now(UTC),
            )
            session.add(review)
            await session.flush()

            review_revision = ReviewRevision(
                organization_id=org.id,
                review_id=review.id,
                revision_number=1,
                rating=5,
                body="Great service!",
                content_hash="a" * 64,
            )
            session.add(review_revision)
            await session.flush()

            response = ReviewResponseRevision(
                organization_id=org.id,
                location_id=location.id,
                review_id=review.id,
                review_revision_id=review_revision.id,
                revision_number=1,
                response_text=approved_comment,
                content_hash="b" * 64,
                status="publishing",
                generated_by_type="manual",
                approved_fact_revision_ids=[],
            )
            session.add(response)
            await session.flush()
            response_id = response.id

            from apps.api.app.execution.handlers import _handle_reviews_publish_response

            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=org.id,
                location_id=location.id,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "succeeded"
        assert outcome.result_reference == f"response:{response_id}"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "published"
            assert refreshed.published_at is not None
            assert refreshed.external_response_id is not None
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_verification_mismatch_marks_reconciliation(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """If the re-read reply doesn't match the approved comment, mark reconciliation."""
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.integrations.models import Provider, ProviderResourceMapping
    from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
    from apps.api.app.products.reviews.models import (
        Review,
        ReviewResponseRevision,
        ReviewRevision,
    )

    class FakeMismatchAdapter:
        async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def list_locations(
            self, access_token: str, account_name: str
        ) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
            raise NotImplementedError

        async def patch_location(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def update_review_reply(
            self, access_token: str, review_name: str, comment: str
        ) -> dict[str, Any]:
            return {"comment": comment}

        async def get_review(self, access_token: str, review_name: str) -> dict[str, Any]:
            return {"reviewReply": {"comment": "DIFFERENT CONTENT THAN APPROVED"}}

        async def list_reviews(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def create_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def get_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def list_local_posts(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = FakeMismatchAdapter
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            org = Organization(
                name="Reviews Mismatch Test",
                slug=f"reviews-mismatch-test-{uuid4().hex[:8]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(org)
            await session.flush()

            location = Location(
                organization_id=org.id,
                name="Mismatch Loc",
                slug=f"mismatch-loc-{uuid4().hex[:8]}",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=True,
                version=1,
            )
            session.add(location)
            await session.flush()

            provider = Provider(
                key="google_business_profile",
                name="Google Business Profile",
                status="active",
                capabilities=["reviews.read"],
            )
            session.add(provider)
            await session.flush()

            connection = IntegrationConnection(
                organization_id=org.id,
                provider_id=provider.id,
                status="connected",
            )
            session.add(connection)
            await session.flush()

            account = GBPAccount(
                organization_id=org.id,
                connection_id=connection.id,
                external_account_id="accounts/mm-test",
                display_name="Mismatch Account",
                status="discovered",
            )
            session.add(account)
            await session.flush()

            resource_mapping = ProviderResourceMapping(
                organization_id=org.id,
                connection_id=connection.id,
                resource_type="gbp_location",
                external_resource_id="locations/mm-loc",
                platform_resource_id=location.id,
                status="active",
            )
            session.add(resource_mapping)
            await session.flush()

            gbp_location = GBPLocation(
                organization_id=org.id,
                location_id=location.id,
                connection_id=connection.id,
                account_id=account.id,
                integration_resource_id=resource_mapping.id,
                external_location_id="locations/mm-loc",
                business_name="Mismatch Location",
                mapping_status="confirmed",
                write_enabled=True,
            )
            session.add(gbp_location)
            await session.flush()

            review = Review(
                organization_id=org.id,
                location_id=location.id,
                integration_resource_id=resource_mapping.id,
                external_review_id="review-mm",
                provider="google",
                rating=4,
                status="triaged",
                review_created_at=datetime.now(UTC),
            )
            session.add(review)
            await session.flush()

            review_revision = ReviewRevision(
                organization_id=org.id,
                review_id=review.id,
                revision_number=1,
                rating=4,
                body="Good",
                content_hash="c" * 64,
            )
            session.add(review_revision)
            await session.flush()

            response = ReviewResponseRevision(
                organization_id=org.id,
                location_id=location.id,
                review_id=review.id,
                review_revision_id=review_revision.id,
                revision_number=1,
                response_text="Approved response",
                content_hash="d" * 64,
                status="publishing",
                generated_by_type="manual",
                approved_fact_revision_ids=[],
            )
            session.add(response)
            await session.flush()
            response_id = response.id

            from apps.api.app.execution.handlers import _handle_reviews_publish_response

            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=org.id,
                location_id=location.id,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "VERIFICATION_CONTENT_MISMATCH"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "reconciliation_required"
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.anyio
async def test_reviews_publish_response_requires_response_id() -> None:
    from apps.api.app.execution.handlers import _handle_reviews_publish_response

    outcome = await _handle_reviews_publish_response(
        None,  # type: ignore[arg-type]
        organization_id=uuid4(),
        location_id=None,
        input_document={},
        correlation_id="test",
    )
    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "MISSING_RESPONSE_ID"


# ---------------------------------------------------------------------------
# GBP Local Post: PROCESSING must NOT become verified
# ---------------------------------------------------------------------------


async def _seed_gbp_post_publication(
    session: AsyncSession,
    *,
    provider_post_id: str | None = None,
    publication_status: str = "reserved",
) -> tuple[UUID, str]:
    """Seed the minimum rows for a GBP post handler invocation.

    Returns (post_publication_id, post_resource_name).
    """
    org = Organization(
        name=f"GBP Post {uuid4().hex[:8]}",
        slug=f"gbp-post-{uuid4().hex[:8]}",
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
    session.add(location)
    await session.flush()

    provider = Provider(
        key="google_business_profile",
        name="Google Business Profile",
        status="active",
        capabilities=["profile.read", "profile.write"],
    )
    session.add(provider)
    await session.flush()
    connection = IntegrationConnection(
        organization_id=org.id,
        provider_id=provider.id,
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
        business_name="Example Business - Downtown",
        mapping_status="confirmed",
        write_enabled=True,
        confirmed_by_user_id=profile.id,
        confirmed_at=datetime.now(UTC),
    )
    session.add(gbp_location)
    await session.flush()

    post_revision = GBPPostRevision(
        organization_id=org.id,
        gbp_location_id=gbp_location.id,
        post_key=uuid4(),
        revision=1,
        post_type="STANDARD",
        content="Test post content",
        status="approved",
        created_at=datetime.now(UTC),
    )
    session.add(post_revision)
    await session.flush()

    workflow_definition = WorkflowDefinition(
        key="gbp.publish_post", name="Publish GBP post", owner="gbp", status="active"
    )
    session.add(workflow_definition)
    await session.flush()
    workflow_version = WorkflowVersion(
        definition_id=workflow_definition.id,
        version=1,
        status="approved",
        input_schema={},
        output_schema={},
        step_specification=[],
        retry_policy={},
        timeout_seconds=60,
    )
    session.add(workflow_version)
    await session.flush()
    workflow_run = WorkflowRun(
        organization_id=org.id,
        location_id=location.id,
        workflow_version_id=workflow_version.id,
        product_key="gbp",
        status="queued",
        trigger_type="api",
        idempotency_key=f"gbp-post-test-run-{uuid4().hex[:8]}",
        request_hash="c" * 64,
        input_document={},
        correlation_id="gbp-post-handler-test",
    )
    session.add(workflow_run)
    await session.flush()

    post_resource_name = "accounts/123/locations/456/localPosts/abc123"
    post_pub = GBPPostPublication(
        organization_id=org.id,
        post_revision_id=post_revision.id,
        workflow_run_id=workflow_run.id,
        idempotency_key=f"gbp-post-test-pub-{uuid4().hex[:8]}",
        status=publication_status,
        provider_post_id=provider_post_id,
    )
    session.add(post_pub)
    await session.flush()
    return post_pub.id, post_resource_name


def _make_stateful_post_adapter(
    *,
    create_state: str = "PROCESSING",
    get_state: str = "PROCESSING",
    post_resource_name: str = "accounts/123/locations/456/localPosts/abc123",
) -> type:
    """Build a fake adapter whose create/get return the given states."""

    class _StatefulPostAdapter:
        async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def list_locations(
            self, access_token: str, account_name: str
        ) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
            raise NotImplementedError

        async def patch_location(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def update_review_reply(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def get_review(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def list_reviews(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def create_local_post(
            self, access_token: str, location_name: str, post_body: dict[str, Any]
        ) -> dict[str, Any]:
            return {"name": post_resource_name, "state": create_state, "postType": "STANDARD"}

        async def get_local_post(self, access_token: str, post_name: str) -> dict[str, Any]:
            return {"name": post_name, "state": get_state, "postType": "STANDARD"}

        async def list_local_posts(
            self, access_token: str, location_name: str
        ) -> list[dict[str, Any]]:
            raise NotImplementedError

    return _StatefulPostAdapter


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_publish_post_processing_state_does_not_become_verified(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A freshly created post in PROCESSING state must NOT be marked verified.

    PROCESSING means Google accepted the post but it is still under
    moderation review — it may later be REJECTED. Treating PROCESSING as
    verified would misreport a post that could be rejected. The handler
    must mark it reconciliation_required so a later retry re-reads the
    same provider resource (provider_post_id is already persisted)
    without creating a duplicate post.
    """
    from apps.api.app.execution import handlers as handler_mod

    fake_adapter_cls = _make_stateful_post_adapter(
        create_state="PROCESSING", get_state="PROCESSING"
    )
    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = fake_adapter_cls
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            post_pub_id, _name = await _seed_gbp_post_publication(session)

            publication = await session.get(GBPPostPublication, post_pub_id)
            assert publication is not None
            outcome = await _handle_gbp_publish_post(
                session,
                organization_id=publication.organization_id,
                location_id=None,
                input_document={"publication_id": str(post_pub_id)},
                correlation_id="test",
            )

        assert outcome.result == "retryable_failure"
        assert outcome.safe_error == "POST_NOT_YET_LIVE"

        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPostPublication, post_pub_id)
            assert refreshed is not None
            assert refreshed.status == "reconciliation_required"
            assert refreshed.verified_at is None
            # provider_post_id IS persisted so a retry re-reads, never duplicates
            assert refreshed.provider_post_id is not None
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_publish_post_processing_reread_does_not_become_verified(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Re-reading a post that is still PROCESSING (from a prior attempt)
    must NOT become verified. It stays reconciliation_required for a
    later retry."""
    from apps.api.app.execution import handlers as handler_mod

    post_resource_name = "accounts/123/locations/456/localPosts/existing"
    fake_adapter_cls = _make_stateful_post_adapter(
        get_state="PROCESSING", post_resource_name=post_resource_name
    )
    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = fake_adapter_cls
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            post_pub_id, _name = await _seed_gbp_post_publication(
                session,
                provider_post_id=post_resource_name,
                publication_status="reconciliation_required",
            )

            publication = await session.get(GBPPostPublication, post_pub_id)
            assert publication is not None
            outcome = await _handle_gbp_publish_post(
                session,
                organization_id=publication.organization_id,
                location_id=None,
                input_document={"publication_id": str(post_pub_id)},
                correlation_id="test",
            )

        assert outcome.result == "retryable_failure"
        assert outcome.safe_error == "POST_NOT_YET_LIVE"

        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPostPublication, post_pub_id)
            assert refreshed is not None
            assert refreshed.status == "reconciliation_required"
            assert refreshed.verified_at is None
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_publish_post_processing_then_live_becomes_verified_on_retry(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A post that was PROCESSING (reconciliation_required) becomes verified
    once a retry re-reads it as LIVE. Proves no duplicate post is created:
    the retry re-reads the existing provider_post_id."""
    from apps.api.app.execution import handlers as handler_mod

    post_resource_name = "accounts/123/locations/456/localPosts/existing"
    fake_adapter_cls = _make_stateful_post_adapter(
        get_state="LIVE", post_resource_name=post_resource_name
    )
    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = fake_adapter_cls
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            post_pub_id, _name = await _seed_gbp_post_publication(
                session,
                provider_post_id=post_resource_name,
                publication_status="reconciliation_required",
            )

            publication = await session.get(GBPPostPublication, post_pub_id)
            assert publication is not None
            outcome = await _handle_gbp_publish_post(
                session,
                organization_id=publication.organization_id,
                location_id=None,
                input_document={"publication_id": str(post_pub_id)},
                correlation_id="test",
            )

        assert outcome.result == "succeeded"
        assert outcome.result_reference == f"publication:{post_pub_id}"

        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPostPublication, post_pub_id)
            assert refreshed is not None
            assert refreshed.status == "verified"
            assert refreshed.verified_at is not None
            assert refreshed.provider_post_id == post_resource_name
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_publish_post_rejected_remains_failed(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A post re-read as REJECTED must become failed (not verified)."""
    from apps.api.app.execution import handlers as handler_mod

    post_resource_name = "accounts/123/locations/456/localPosts/rejected"
    fake_adapter_cls = _make_stateful_post_adapter(
        get_state="REJECTED", post_resource_name=post_resource_name
    )
    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = fake_adapter_cls
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            post_pub_id, _name = await _seed_gbp_post_publication(
                session,
                provider_post_id=post_resource_name,
                publication_status="reconciliation_required",
            )

            publication = await session.get(GBPPostPublication, post_pub_id)
            assert publication is not None
            outcome = await _handle_gbp_publish_post(
                session,
                organization_id=publication.organization_id,
                location_id=None,
                input_document={"publication_id": str(post_pub_id)},
                correlation_id="test",
            )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "POST_REJECTED_BY_PROVIDER"

        async with clean_session_factory() as session:
            refreshed = await session.get(GBPPostPublication, post_pub_id)
            assert refreshed is not None
            assert refreshed.status == "failed"
            assert refreshed.verified_at is None
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


# ---------------------------------------------------------------------------
# Reviews publish-response: safe_error_code consistency
# ---------------------------------------------------------------------------


async def _seed_review_response_publication(
    session: AsyncSession,
    *,
    include_mapping: bool = True,
    mapping_active: bool = True,
    include_gbp_location: bool = True,
    include_gbp_account: bool = True,
    include_connection: bool = True,
    response_status: str = "publishing",
) -> UUID:
    """Seed the minimum rows for a review-response handler invocation.

    Flags control which governed mapping rows are created, so individual
    failure paths (PROVIDER_MAPPING_NOT_FOUND, GBP_LOCATION_NOT_FOUND,
    GBP_ACCOUNT_NOT_FOUND, NO_CONNECTED_INTEGRATION) can be exercised.
    """
    from apps.api.app.integrations.models import (
        IntegrationConnection,
        Provider,
        ProviderResourceMapping,
    )
    from apps.api.app.products.reviews.models import (
        Review,
        ReviewResponseRevision,
        ReviewRevision,
    )

    org = Organization(
        name=f"Reviews Handler {uuid4().hex[:8]}",
        slug=f"reviews-handler-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()

    location = Location(
        organization_id=org.id,
        name="Reviews Handler Loc",
        slug=f"reviews-handler-loc-{uuid4().hex[:8]}",
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url="https://example.invalid",
        is_primary=True,
        version=1,
    )
    session.add(location)
    await session.flush()

    mapping_id: UUID | None = None
    if include_mapping:
        provider = Provider(
            key="google_business_profile",
            name="Google Business Profile",
            status="active",
            capabilities=["reviews.read"],
        )
        session.add(provider)
        await session.flush()
        connection = IntegrationConnection(
            organization_id=org.id,
            provider_id=provider.id,
            status="connected" if include_connection else "disconnected",
        )
        session.add(connection)
        await session.flush()
        mapping = ProviderResourceMapping(
            organization_id=org.id,
            connection_id=connection.id,
            resource_type="gbp_location",
            external_resource_id="locations/rev-loc",
            platform_resource_id=location.id,
            status="active" if mapping_active else "stale",
        )
        session.add(mapping)
        await session.flush()
        mapping_id = mapping.id

        if include_gbp_location:
            account = GBPAccount(
                organization_id=org.id,
                connection_id=connection.id,
                external_account_id="accounts/rev-test",
                display_name="Review Test Account",
                status="discovered",
            )
            session.add(account)
            await session.flush()

            gbp_location = GBPLocation(
                organization_id=org.id,
                location_id=location.id,
                connection_id=connection.id,
                account_id=account.id if include_gbp_account else uuid4(),
                integration_resource_id=mapping.id,
                external_location_id="locations/rev-loc",
                business_name="Review Test Location",
                mapping_status="confirmed",
                write_enabled=True,
            )
            session.add(gbp_location)
            await session.flush()

    review = Review(
        organization_id=org.id,
        location_id=location.id,
        integration_resource_id=mapping_id or uuid4(),
        external_review_id=f"review-{uuid4().hex[:8]}",
        provider="google",
        rating=5,
        status="triaged",
        review_created_at=datetime.now(UTC),
    )
    session.add(review)
    await session.flush()

    review_revision = ReviewRevision(
        organization_id=org.id,
        review_id=review.id,
        revision_number=1,
        rating=5,
        body="Great service!",
        content_hash="a" * 64,
    )
    session.add(review_revision)
    await session.flush()

    response = ReviewResponseRevision(
        organization_id=org.id,
        location_id=location.id,
        review_id=review.id,
        review_revision_id=review_revision.id,
        revision_number=1,
        response_text="Thank you for your kind words!",
        content_hash="b" * 64,
        status=response_status,
        generated_by_type="manual",
        approved_fact_revision_ids=[],
    )
    session.add(response)
    await session.flush()
    return response.id


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_persists_safe_error_code_provider_mapping_not_found(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """safe_error_code must be persisted as PROVIDER_MAPPING_NOT_FOUND."""
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.products.reviews.models import ReviewResponseRevision

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = _make_stateful_post_adapter  # type: ignore[assignment]
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            # Mapping exists but is stale, so the handler's
            # status == "active" check fails.
            response_id = await _seed_review_response_publication(
                session, include_mapping=True, mapping_active=False
            )

            revision = await session.get(ReviewResponseRevision, response_id)
            assert revision is not None
            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=revision.organization_id,
                location_id=None,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "PROVIDER_MAPPING_NOT_FOUND"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "failed"
            assert refreshed.safe_error_code == "PROVIDER_MAPPING_NOT_FOUND"
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_persists_safe_error_code_gbp_location_not_found(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """safe_error_code must be persisted as GBP_LOCATION_NOT_FOUND."""
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.products.reviews.models import ReviewResponseRevision

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = _make_stateful_post_adapter  # type: ignore[assignment]
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            # Mapping exists but no GBP location links to it.
            response_id = await _seed_review_response_publication(
                session, include_mapping=True, include_gbp_location=False
            )

            revision = await session.get(ReviewResponseRevision, response_id)
            assert revision is not None
            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=revision.organization_id,
                location_id=None,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "GBP_LOCATION_NOT_FOUND"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "failed"
            assert refreshed.safe_error_code == "GBP_LOCATION_NOT_FOUND"
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_persists_safe_error_code_gbp_account_not_found(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """safe_error_code must be persisted as GBP_ACCOUNT_NOT_FOUND when the
    GBP account linked to the location no longer exists.

    The GBP locations FK to gbp_accounts with ondelete=RESTRICT and the
    constraint is NOT DEFERRABLE, so we can't repoint account_id to a
    non-existent row via SQL. Instead, we wrap the session so that
    session.get(GBPAccount, ...) returns None, simulating a deleted
    account that the location still references.
    """
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.products.gbp.models import GBPAccount
    from apps.api.app.products.reviews.models import ReviewResponseRevision

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = _make_stateful_post_adapter  # type: ignore[assignment]
    handler_mod._token_resolver = _fake_token_resolver
    try:
        response_id: UUID | None = None
        async with clean_session_factory.begin() as session:
            response_id = await _seed_review_response_publication(session)

            response = await session.get(ReviewResponseRevision, response_id)
            assert response is not None

            # Wrap session.get to simulate a missing GBPAccount. The wrapper
            # accepts the same flexible signature shape as the bound
            # AsyncSession.get method so the assignment stays type-correct;
            # the method-assignment ignore records that we are intentionally
            # shadowing a bound method for the duration of this session.
            original_get = session.get

            async def _fake_get(*args: Any, **kwargs: Any) -> Any:
                if args and args[0] is GBPAccount:
                    return None
                return await original_get(*args, **kwargs)

            session.get = _fake_get  # type: ignore[method-assign]

            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=response.organization_id,
                location_id=None,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "GBP_ACCOUNT_NOT_FOUND"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "failed"
            assert refreshed.safe_error_code == "GBP_ACCOUNT_NOT_FOUND"
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_persists_safe_error_code_no_connected_integration(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """safe_error_code must be persisted as NO_CONNECTED_INTEGRATION when
    the token resolver raises IntegrationNotFoundError."""
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.integrations.errors import IntegrationNotFoundError
    from apps.api.app.products.reviews.models import ReviewResponseRevision

    async def _failing_token_resolver(
        session: AsyncSession, organization_id: UUID
    ) -> tuple[str, object]:
        raise IntegrationNotFoundError

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = _make_stateful_post_adapter  # type: ignore[assignment]
    handler_mod._token_resolver = _failing_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            response_id = await _seed_review_response_publication(session)

            revision = await session.get(ReviewResponseRevision, response_id)
            assert revision is not None
            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=revision.organization_id,
                location_id=None,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "NO_CONNECTED_INTEGRATION"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "failed"
            assert refreshed.safe_error_code == "NO_CONNECTED_INTEGRATION"
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_persists_safe_error_code_provider_write_failed(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """safe_error_code must be persisted as PROVIDER_WRITE_FAILED when the
    adapter's update_review_reply raises."""
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.products.reviews.models import ReviewResponseRevision

    class _WriteFailsAdapter:
        async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def list_locations(
            self, access_token: str, account_name: str
        ) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
            raise NotImplementedError

        async def patch_location(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def update_review_reply(
            self, access_token: str, review_name: str, comment: str
        ) -> dict[str, Any]:
            raise RuntimeError("provider write failed")

        async def get_review(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def list_reviews(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def create_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def get_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def list_local_posts(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = _WriteFailsAdapter
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            response_id = await _seed_review_response_publication(session)

            revision = await session.get(ReviewResponseRevision, response_id)
            assert revision is not None
            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=revision.organization_id,
                location_id=None,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "retryable_failure"
        assert outcome.safe_error == "PROVIDER_WRITE_FAILED"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "failed"
            assert refreshed.safe_error_code == "PROVIDER_WRITE_FAILED"
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_persists_safe_error_code_token_refresh_failed(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """safe_error_code must be persisted as TOKEN_REFRESH_FAILED when the
    token resolver raises IntegrationReconnectRequiredError."""
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.integrations.errors import IntegrationReconnectRequiredError
    from apps.api.app.products.reviews.models import ReviewResponseRevision

    async def _reconnect_required_resolver(
        session: AsyncSession, organization_id: UUID
    ) -> tuple[str, object]:
        raise IntegrationReconnectRequiredError

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = _make_stateful_post_adapter  # type: ignore[assignment]
    handler_mod._token_resolver = _reconnect_required_resolver
    try:
        async with clean_session_factory.begin() as session:
            response_id = await _seed_review_response_publication(session)

            revision = await session.get(ReviewResponseRevision, response_id)
            assert revision is not None
            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=revision.organization_id,
                location_id=None,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "retryable_failure"
        assert outcome.safe_error == "TOKEN_REFRESH_FAILED"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "reconciliation_required"
            assert refreshed.safe_error_code == "TOKEN_REFRESH_FAILED"
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_reviews_publish_response_persists_safe_error_code_verification_reread_failed(
    clean_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """safe_error_code must be persisted as VERIFICATION_REREAD_FAILED when
    the adapter's get_review raises after a successful write."""
    from apps.api.app.execution import handlers as handler_mod
    from apps.api.app.products.reviews.models import ReviewResponseRevision

    class _RereadFailsAdapter:
        async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def list_locations(
            self, access_token: str, account_name: str
        ) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
            raise NotImplementedError

        async def patch_location(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def update_review_reply(
            self, access_token: str, review_name: str, comment: str
        ) -> dict[str, Any]:
            return {"comment": comment}

        async def get_review(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise RuntimeError("re-read failed")

        async def list_reviews(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

        async def create_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def get_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
            raise NotImplementedError

        async def list_local_posts(self, *args: object, **kwargs: object) -> list[dict[str, Any]]:
            raise NotImplementedError

    original = handler_mod._adapter_factory
    original_resolver = handler_mod._token_resolver
    handler_mod._adapter_factory = _RereadFailsAdapter
    handler_mod._token_resolver = _fake_token_resolver
    try:
        async with clean_session_factory.begin() as session:
            response_id = await _seed_review_response_publication(session)

            revision = await session.get(ReviewResponseRevision, response_id)
            assert revision is not None
            outcome = await _handle_reviews_publish_response(
                session,
                organization_id=revision.organization_id,
                location_id=None,
                input_document={"response_id": str(response_id)},
                correlation_id="test",
            )

        assert outcome.result == "retryable_failure"
        assert outcome.safe_error == "VERIFICATION_REREAD_FAILED"

        async with clean_session_factory() as session:
            refreshed = await session.get(ReviewResponseRevision, response_id)
            assert refreshed is not None
            assert refreshed.status == "reconciliation_required"
            assert refreshed.safe_error_code == "VERIFICATION_REREAD_FAILED"
    finally:
        handler_mod._adapter_factory = original
        handler_mod._token_resolver = original_resolver
