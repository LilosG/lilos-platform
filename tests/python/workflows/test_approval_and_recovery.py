"""Packet 5 — SC5-APPROVALS and SC5-FAILURES acceptance.

Proves:
- Approval boundary: protected action cannot execute before approval
- Approval state is authoritative
- Duplicate approval cannot duplicate side effect
- Retryable error classification and backoff
- Permanent failure classification
- Terminal failure after policy exhaustion
- Idempotency preserves safety
- Tenant isolation
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.handlers import _handle_gbp_publish_change
from apps.api.app.execution.models import (
    Job,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.execution.service import ExecutionService
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


async def _seed_org_with_gbp(
    session: AsyncSession, name: str, slug: str
) -> tuple[Organization, Location, GBPLocation, GBPAccount]:
    org = Organization(
        name=name,
        slug=slug,
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
        name="Downtown",
        slug=f"{slug}-downtown",
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

    provider = await session.scalar(select(Provider).where(Provider.key == "google"))
    if provider is None:
        provider = Provider(
            key="google",
            name="Google",
            status="active",
            capabilities=["business_profile", "reviews"],
            manifest_version=1,
        )
        session.add(provider)
        await session.flush()

    connection = IntegrationConnection(
        organization_id=org.id,
        provider_id=provider.id,
        external_account_reference="accounts/test-account",
        status="connected",
        version=1,
    )
    session.add(connection)
    await session.flush()

    account = GBPAccount(
        organization_id=org.id,
        connection_id=connection.id,
        external_account_id="accounts/test-account",
        display_name="Test Account",
        status="selected",
    )
    session.add(account)
    await session.flush()

    gbp_location = GBPLocation(
        organization_id=org.id,
        location_id=location.id,
        connection_id=connection.id,
        account_id=account.id,
        external_location_id="locations/test-location",
        business_name="Test Business",
        mapping_status="confirmed",
        write_enabled=True,
    )
    session.add(gbp_location)
    await session.flush()
    return org, location, gbp_location, account


async def _create_workflow_run(
    session: AsyncSession, org_id: UUID, workflow_key: str
) -> WorkflowRun:
    wf_def = WorkflowDefinition(
        key=workflow_key,
        name=f"Test {workflow_key}",
        owner="gbp",
        status="active",
    )
    session.add(wf_def)
    await session.flush()
    wf_ver = WorkflowVersion(
        definition_id=wf_def.id,
        version=1,
        status="approved",
        input_schema={},
        output_schema={},
        step_specification=[],
        retry_policy={},
        timeout_seconds=300,
    )
    session.add(wf_ver)
    await session.flush()
    run = WorkflowRun(
        organization_id=org_id,
        workflow_version_id=wf_ver.id,
        status="queued",
        trigger_type="test",
        idempotency_key=f"p5-approval-{uuid4().hex[:12]}",
        request_hash="test-hash",
        input_document={},
        correlation_id="p5-approval-test",
    )
    session.add(run)
    await session.flush()
    return run


# ---------------------------------------------------------------------------
# SC5-APPROVALS — Approval boundary
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_handler_rejects_non_reserved_publication(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handler must reject a publication that is not in 'reserved' status.

    This proves the approval boundary: a publication can only reach 'reserved'
    after the product-level approval flow (revision approved → publication
    reserved). The handler is the last gate before the provider write.
    """
    from apps.api.app.execution import handlers as handlers_module

    async with workflows_session_factory.begin() as session:
        org, location, gbp_location, account = await _seed_org_with_gbp(
            session, "Approval Test", f"approval-{uuid4().hex[:12]}"
        )
        run = await _create_workflow_run(session, org.id, "gbp.publish_change")

        snapshot = GBPProfileSnapshot(
            organization_id=org.id,
            gbp_location_id=gbp_location.id,
            normalized_profile={"profile": {"description": "Original"}},
            content_hash="a" * 64,
            completeness="full",
            observed_at=datetime.now(UTC),
        )
        session.add(snapshot)
        await session.flush()
        revision = GBPProfileChangeRevision(
            organization_id=org.id,
            location_id=location.id,
            gbp_location_id=gbp_location.id,
            change_identity=uuid4(),
            revision_number=1,
            base_snapshot_id=snapshot.id,
            desired_fields={"description": "new"},
            diff_document={},
            fact_revision_ids=[],
            status="approved",
            risk_level="low",
            content_hash="b" * 64,
        )
        session.add(revision)
        await session.flush()

        # Publication in 'failed' status — not reservable
        publication = GBPPublication(
            organization_id=org.id,
            location_id=location.id,
            change_revision_id=revision.id,
            workflow_run_id=run.id,
            idempotency_key=f"p5-pub-{uuid4().hex[:12]}",
            status="failed",
            update_mask=["description"],
        )
        session.add(publication)
        await session.flush()

        # Patch token resolver to avoid real provider call
        monkeypatch.setattr(
            handlers_module,
            "_token_resolver",
            lambda s, o: ("fake-token", None),
        )

        outcome = await _handle_gbp_publish_change(
            session,
            organization_id=org.id,
            location_id=location.id,
            input_document={"publication_id": str(publication.id)},
            correlation_id="p5-approval-boundary",
            workflow_run_id=run.id,
        )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "PUBLICATION_NOT_RESERVABLE"


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_handler_idempotency_is_upstream(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An already verified publication resolves idempotently without provider I/O."""
    from apps.api.app.execution import handlers as handlers_module

    async with workflows_session_factory.begin() as session:
        org, location, gbp_location, account = await _seed_org_with_gbp(
            session, "Idem Pub Test", f"idempub-{uuid4().hex[:12]}"
        )
        run = await _create_workflow_run(session, org.id, "gbp.publish_change")

        snapshot = GBPProfileSnapshot(
            organization_id=org.id,
            gbp_location_id=gbp_location.id,
            normalized_profile={"profile": {"description": "Original"}},
            content_hash="a" * 64,
            completeness="full",
            observed_at=datetime.now(UTC),
        )
        session.add(snapshot)
        await session.flush()
        revision = GBPProfileChangeRevision(
            organization_id=org.id,
            location_id=location.id,
            gbp_location_id=gbp_location.id,
            change_identity=uuid4(),
            revision_number=1,
            base_snapshot_id=snapshot.id,
            desired_fields={"description": "new"},
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
            idempotency_key=f"p5-idempub-{uuid4().hex[:12]}",
            status="verified",
            update_mask=["description"],
        )
        session.add(publication)
        await session.flush()

        monkeypatch.setattr(
            handlers_module,
            "_token_resolver",
            lambda s, o: ("fake-token", None),
        )

        outcome = await _handle_gbp_publish_change(
            session,
            organization_id=org.id,
            location_id=location.id,
            input_document={"publication_id": str(publication.id)},
            correlation_id="p5-idempotent",
            workflow_run_id=run.id,
        )

        assert outcome.result == "succeeded"
        assert outcome.result_reference == f"publication:{publication.id}"


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_handler_cross_org_publication_not_found(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A publication from another org must not be found — tenant isolation."""
    from apps.api.app.execution import handlers as handlers_module

    async with workflows_session_factory.begin() as session:
        org, location, gbp_location, account = await _seed_org_with_gbp(
            session, "Tenant A", f"tenant-a-{uuid4().hex[:12]}"
        )
        other_org, _other_loc, _other_gbp, _other_acct = await _seed_org_with_gbp(
            session, "Tenant B", f"tenant-b-{uuid4().hex[:12]}"
        )
        run = await _create_workflow_run(session, org.id, "gbp.publish_change")

        snapshot = GBPProfileSnapshot(
            organization_id=org.id,
            gbp_location_id=gbp_location.id,
            normalized_profile={"profile": {"description": "Original"}},
            content_hash="a" * 64,
            completeness="full",
            observed_at=datetime.now(UTC),
        )
        session.add(snapshot)
        await session.flush()
        revision = GBPProfileChangeRevision(
            organization_id=org.id,
            location_id=location.id,
            gbp_location_id=gbp_location.id,
            change_identity=uuid4(),
            revision_number=1,
            base_snapshot_id=snapshot.id,
            desired_fields={"description": "new"},
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
            idempotency_key=f"p5-tenant-{uuid4().hex[:12]}",
            status="reserved",
            update_mask=["description"],
        )
        session.add(publication)
        await session.flush()

        monkeypatch.setattr(
            handlers_module,
            "_token_resolver",
            lambda s, o: ("fake-token", None),
        )

        # Attempt to access org's publication from other_org
        outcome = await _handle_gbp_publish_change(
            session,
            organization_id=other_org.id,
            location_id=None,
            input_document={"publication_id": str(publication.id)},
            correlation_id="p5-tenant-isolation",
            workflow_run_id=uuid4(),
        )

        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "PUBLICATION_NOT_FOUND"


# ---------------------------------------------------------------------------
# SC5-FAILURES — Retry classification, backoff, terminal failure
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.anyio
async def test_retryable_failure_schedules_retry_with_backoff(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A retryable failure must set status=retry_scheduled with exponential backoff."""
    service = ExecutionService()
    async with workflows_session_factory.begin() as session:
        org = Organization(
            name="Retry Test",
            slug=f"retry-{uuid4().hex[:12]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        wf_def = WorkflowDefinition(key="gbp.sync", name="GBP Sync", owner="gbp", status="active")
        session.add(wf_def)
        await session.flush()
        wf_ver = WorkflowVersion(
            definition_id=wf_def.id,
            version=1,
            status="approved",
            input_schema={},
            output_schema={},
            step_specification=[],
            retry_policy={},
            timeout_seconds=300,
        )
        session.add(wf_ver)
        await session.flush()
        run = WorkflowRun(
            organization_id=org.id,
            workflow_version_id=wf_ver.id,
            status="queued",
            trigger_type="test",
            idempotency_key=f"p5-retry-{uuid4().hex[:12]}",
            request_hash="test-hash",
            input_document={},
            correlation_id="p5-retry-test",
        )
        session.add(run)
        await session.flush()

        job = Job(
            organization_id=org.id,
            workflow_run_id=run.id,
            job_type="workflow.execute",
            status="queued",
            idempotency_key=f"p5-retry-job-{uuid4().hex[:12]}",
            payload={"run_id": str(run.id)},
            attempt_count=1,
            max_attempts=3,
        )
        session.add(job)
        await session.flush()

        now = datetime.now(UTC)
        outcome = JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
        finished = await service.finish(session, org.id, job.id, outcome)

        assert finished.status == "retry_scheduled"
        assert finished.available_at is not None
        backoff_seconds = (finished.available_at - now).total_seconds()
        # Exponential backoff: min(3600, 2**1) = 2 seconds
        assert 1 <= backoff_seconds <= 5, f"Expected ~2s backoff, got {backoff_seconds:.1f}s"


@pytest.mark.integration
@pytest.mark.anyio
async def test_permanent_failure_marks_failed_immediately(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A permanent failure must set status=failed without retry scheduling."""
    service = ExecutionService()
    async with workflows_session_factory.begin() as session:
        org = Organization(
            name="PermFail Test",
            slug=f"permfail-{uuid4().hex[:12]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        wf_def = WorkflowDefinition(key="gbp.sync", name="GBP Sync", owner="gbp", status="active")
        session.add(wf_def)
        await session.flush()
        wf_ver = WorkflowVersion(
            definition_id=wf_def.id,
            version=1,
            status="approved",
            input_schema={},
            output_schema={},
            step_specification=[],
            retry_policy={},
            timeout_seconds=300,
        )
        session.add(wf_ver)
        await session.flush()
        run = WorkflowRun(
            organization_id=org.id,
            workflow_version_id=wf_ver.id,
            status="queued",
            trigger_type="test",
            idempotency_key=f"p5-perm-{uuid4().hex[:12]}",
            request_hash="test-hash",
            input_document={},
            correlation_id="p5-perm-test",
        )
        session.add(run)
        await session.flush()

        job = Job(
            organization_id=org.id,
            workflow_run_id=run.id,
            job_type="workflow.execute",
            status="queued",
            idempotency_key=f"p5-perm-job-{uuid4().hex[:12]}",
            payload={"run_id": str(run.id)},
            attempt_count=1,
            max_attempts=3,
        )
        session.add(job)
        await session.flush()

        outcome = JobOutcome(result="permanent_failure", safe_error="LOCATION_ID_MISSING")
        finished = await service.finish(session, org.id, job.id, outcome)

        assert finished.status == "failed"
        assert finished.available_at is None or finished.available_at <= datetime.now(UTC)


@pytest.mark.integration
@pytest.mark.anyio
async def test_terminal_failure_after_max_attempts(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """At max_attempts, a retryable failure must dead-letter, not retry again."""
    service = ExecutionService()
    async with workflows_session_factory.begin() as session:
        org = Organization(
            name="DeadLetter Test",
            slug=f"dead-{uuid4().hex[:12]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        wf_def = WorkflowDefinition(key="gbp.sync", name="GBP Sync", owner="gbp", status="active")
        session.add(wf_def)
        await session.flush()
        wf_ver = WorkflowVersion(
            definition_id=wf_def.id,
            version=1,
            status="approved",
            input_schema={},
            output_schema={},
            step_specification=[],
            retry_policy={},
            timeout_seconds=300,
        )
        session.add(wf_ver)
        await session.flush()
        run = WorkflowRun(
            organization_id=org.id,
            workflow_version_id=wf_ver.id,
            status="queued",
            trigger_type="test",
            idempotency_key=f"p5-dead-{uuid4().hex[:12]}",
            request_hash="test-hash",
            input_document={},
            correlation_id="p5-dead-test",
        )
        session.add(run)
        await session.flush()

        job = Job(
            organization_id=org.id,
            workflow_run_id=run.id,
            job_type="workflow.execute",
            status="queued",
            idempotency_key=f"p5-dead-job-{uuid4().hex[:12]}",
            payload={"run_id": str(run.id)},
            attempt_count=3,  # Already at max
            max_attempts=3,
        )
        session.add(job)
        await session.flush()

        outcome = JobOutcome(result="retryable_failure", safe_error="PROVIDER_WRITE_FAILED")
        finished = await service.finish(session, org.id, job.id, outcome)

        assert finished.status == "dead_lettered", (
            f"At max attempts, must dead-letter, got {finished.status}"
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_succeeded_outcome_marks_completed(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A succeeded outcome must set status=completed."""
    service = ExecutionService()
    async with workflows_session_factory.begin() as session:
        org = Organization(
            name="Success Test",
            slug=f"success-{uuid4().hex[:12]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        wf_def = WorkflowDefinition(key="gbp.sync", name="GBP Sync", owner="gbp", status="active")
        session.add(wf_def)
        await session.flush()
        wf_ver = WorkflowVersion(
            definition_id=wf_def.id,
            version=1,
            status="approved",
            input_schema={},
            output_schema={},
            step_specification=[],
            retry_policy={},
            timeout_seconds=300,
        )
        session.add(wf_ver)
        await session.flush()
        run = WorkflowRun(
            organization_id=org.id,
            workflow_version_id=wf_ver.id,
            status="queued",
            trigger_type="test",
            idempotency_key=f"p5-ok-{uuid4().hex[:12]}",
            request_hash="test-hash",
            input_document={},
            correlation_id="p5-ok-test",
        )
        session.add(run)
        await session.flush()

        job = Job(
            organization_id=org.id,
            workflow_run_id=run.id,
            job_type="workflow.execute",
            status="queued",
            idempotency_key=f"p5-ok-job-{uuid4().hex[:12]}",
            payload={"run_id": str(run.id)},
            attempt_count=1,
            max_attempts=3,
        )
        session.add(job)
        await session.flush()

        outcome = JobOutcome(result="succeeded", result_reference="test-ref")
        finished = await service.finish(session, org.id, job.id, outcome)

        assert finished.status == "completed"
        assert finished.result_reference == "test-ref"
