"""Production-capable Content route, audit, notification, and isolation tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.main import create_app
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import PublishingTarget


class FakeVerifier:
    def __init__(self, claims: VerifiedProviderClaims) -> None:
        self.result: VerifiedProviderClaims | Exception = claims

    async def verify(self, token: str) -> VerifiedProviderClaims:
        del token
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def claims(
    subject: UUID, assurance: AssuranceLevel = AssuranceLevel.AAL2
) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=uuid4(),
        assurance_level=assurance,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="content-test-key",
    )


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.fixture
def content_client(
    postgresql_test_url: str,
    content_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with content_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="content-api-catalog")
            organization = Organization(
                name="Content Test Org",
                slug="content-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="Content Other Org",
                slug="content-other-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add_all([organization, other_organization, profile])
            await session.flush()

            location = Location(
                organization_id=organization.id,
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

            membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="content-api-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="content-api-owner",
            )

            provider = Provider(
                key="github", name="GitHub", status="active", capabilities=["content.publish"]
            )
            session.add(provider)
            await session.flush()
            connection = IntegrationConnection(
                organization_id=organization.id,
                provider_id=provider.id,
                external_account_reference="org/site-repo",
                status="connected",
            )
            session.add(connection)
            await session.flush()
            target = PublishingTarget(
                organization_id=organization.id,
                connection_id=connection.id,
                key="primary",
                target_type="github_astro",
                repository_id="org/site-repo",
                base_branch="main",
                allowed_path_prefix="src/content",
                status="active",
                version=1,
            )
            session.add(target)
            await session.flush()

            workflow_definition = WorkflowDefinition(
                key="content.publish", name="Publish content", owner="content"
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
                organization_id=organization.id,
                location_id=location.id,
                workflow_version_id=workflow_version.id,
                product_key="content",
                trigger_type="manual",
                idempotency_key="content-test-workflow-run-001",
                request_hash="deterministic-request-hash",
                input_document={},
                correlation_id="content-test-workflow",
            )
            session.add(workflow_run)
            await session.flush()

            approved_fact = BusinessFactRevision(
                organization_id=organization.id,
                location_id=location.id,
                fact_identity=uuid4(),
                fact_key="business.name",
                value_type="string",
                value="Winter HVAC Pros",
                source="client_input",
                authority="client_approved",
                status="approved",
                revision=1,
                proposed_by=profile.id,
                approved_by=profile.id,
                approved_at=datetime.now(UTC),
                change_reason="Content API test fixture",
            )
            session.add(approved_fact)
            await session.flush()

            identifiers = {
                "organization": organization.id,
                "other_organization": other_organization.id,
                "location": location.id,
                "assigned_subject": profile.auth_user_id,
                "target": target.id,
                "workflow_run": workflow_run.id,
                "approved_fact": approved_fact.id,
            }
            return claims(profile.auth_user_id), identifiers

    verified, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(verified)
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "database_url": postgresql_test_url,
            "secret_encryption_key": Fernet.generate_key().decode("utf-8"),
        }
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, identifiers


@pytest.mark.integration
def test_opportunity_item_brief_manual_revision_approval_and_publication_flow(
    content_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = content_client
    org, location, target = ids["organization"], ids["location"], ids["target"]
    base = f"/api/v1/organizations/{org}/content"

    opportunity = client.post(
        f"{base}/opportunities",
        headers=HEADERS,
        json={
            "location_id": str(location),
            "product_key": "seo",
            "target_reference": "/services/plumbing",
            "opportunity_type": "keyword_gap",
            "source_type": "seo_analysis",
            "source_reference": "seo-report-1",
            "evidence_document": {"keyword": "emergency plumbing"},
            "priority_score": 80,
        },
    )
    assert opportunity.status_code == 201, opportunity.text
    opportunity_id = opportunity.json()["data"]["id"]

    listing = client.get(f"{base}/opportunities", headers=HEADERS)
    assert listing.status_code == 200
    assert listing.headers["Cache-Control"] == "no-store"
    assert len(listing.json()["data"]) == 1

    decision = client.post(
        f"{base}/opportunities/{opportunity_id}/decision", headers=HEADERS, json={"accept": True}
    )
    assert decision.status_code == 200
    assert decision.json()["data"]["status"] == "accepted"

    item = client.post(
        base,
        headers=HEADERS,
        json={
            "opportunity_id": opportunity_id,
            "location_id": str(location),
            "content_type": "landing_page",
            "title": "Emergency Plumbing Services",
            "slug": "emergency-plumbing-services",
        },
    )
    assert item.status_code == 201, item.text
    item_id = item.json()["data"]["id"]
    assert item.json()["data"]["status"] == "briefing"

    detail = client.get(f"{base}/{item_id}", headers=HEADERS)
    assert detail.status_code == 200

    brief = client.post(
        f"{base}/{item_id}/briefs",
        headers=HEADERS,
        json={
            "audience": "Homeowners with an emergency plumbing issue",
            "intent": "convert",
            "target_reference": "/services/plumbing",
            "approved_fact_revision_ids": [str(uuid4())],
        },
    )
    assert brief.status_code == 201, brief.text

    manual = client.post(
        f"{base}/{item_id}/revisions",
        headers=HEADERS,
        json={
            "body": "# Emergency Plumbing\n\nWe respond fast.",
            "frontmatter": {"title": "Emergency Plumbing"},
            "created_by_type": "user",
            "approved_fact_revision_ids": [str(uuid4())],
        },
    )
    assert manual.status_code == 201, manual.text
    revision_id = manual.json()["data"]["id"]
    assert manual.json()["data"]["status"] == "awaiting_editorial"

    editorial = client.post(
        f"{base}/{item_id}/revisions/{revision_id}/decision",
        headers=HEADERS,
        json={"stage": "editorial", "approve": True},
    )
    assert editorial.status_code == 200
    assert editorial.json()["data"]["status"] == "awaiting_client"

    client_approval = client.post(
        f"{base}/{item_id}/revisions/{revision_id}/decision",
        headers=HEADERS,
        json={"stage": "client", "approve": True},
    )
    assert client_approval.status_code == 200
    assert client_approval.json()["data"]["status"] == "approved"

    publish = client.post(
        f"{base}/{item_id}/revisions/{revision_id}/publish",
        headers=HEADERS,
        json={
            "publishing_target_id": str(target),
            "workflow_run_id": str(ids["workflow_run"]),
            "target_path": "src/content/services/emergency-plumbing.md",
            "idempotency_key": "content-publish-key-001",
        },
    )
    assert publish.status_code == 202, publish.text
    assert publish.json()["data"]["status"] == "reserved"

    publications = client.get(f"{base}/{item_id}/publications", headers=HEADERS)
    assert publications.status_code == 200
    assert len(publications.json()["data"]) == 1

    audit = client.get(f"{base}/{item_id}/audit", headers=HEADERS)
    assert audit.status_code == 200
    event_types = {event["event_type"] for event in audit.json()["data"]}
    assert {
        "content.item.created",
        "content.brief.created",
        "content.revision.drafted",
        "content.publication.reserved",
    } <= event_types

    revision_audit = client.get(f"{base}/revisions/{revision_id}/audit", headers=HEADERS)
    assert revision_audit.status_code == 200
    revision_event_types = {event["event_type"] for event in revision_audit.json()["data"]}
    assert "content.revision.decided" in revision_event_types


@pytest.mark.integration
def test_ai_draft_generates_grounded_revision_requiring_human_review(
    content_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = content_client
    org = ids["organization"]
    approved_fact = ids["approved_fact"]
    base = f"/api/v1/organizations/{org}/content"

    item = client.post(
        base,
        headers=HEADERS,
        json={"content_type": "blog_post", "title": "Winter HVAC Tips", "slug": "winter-hvac-tips"},
    )
    assert item.status_code == 201
    item_id = item.json()["data"]["id"]
    assert item.json()["data"]["status"] == "idea"

    brief = client.post(
        f"{base}/{item_id}/briefs",
        headers=HEADERS,
        json={
            "audience": "Homeowners preparing for winter",
            "intent": "educate",
            "target_reference": "/blog/winter-hvac-tips",
            "approved_fact_revision_ids": [str(approved_fact)],
        },
    )
    brief_id = brief.json()["data"]["id"]

    draft = client.post(
        f"{base}/{item_id}/revisions/ai-draft?sync=true",
        headers=HEADERS,
        json={"brief_id": brief_id, "idempotency_key": "content-ai-draft-key-001"},
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["data"]["requires_human_review"] is True
    assert draft.json()["data"]["body"]
    assert draft.json()["data"]["status"] == "awaiting_editorial"


@pytest.mark.integration
def test_publication_without_configured_target_is_rejected(
    content_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = content_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/content"

    item = client.post(
        base,
        headers=HEADERS,
        json={"content_type": "blog_post", "title": "Untargeted Post", "slug": "untargeted-post"},
    )
    item_id = item.json()["data"]["id"]
    brief = client.post(
        f"{base}/{item_id}/briefs",
        headers=HEADERS,
        json={
            "audience": "General audience",
            "intent": "inform",
            "target_reference": "/blog/untargeted-post",
            "approved_fact_revision_ids": [str(uuid4())],
        },
    )
    del brief
    manual = client.post(
        f"{base}/{item_id}/revisions",
        headers=HEADERS,
        json={
            "body": "Body text",
            "frontmatter": {},
            "created_by_type": "user",
            "approved_fact_revision_ids": [str(uuid4())],
        },
    )
    revision_id = manual.json()["data"]["id"]
    client.post(
        f"{base}/{item_id}/revisions/{revision_id}/decision",
        headers=HEADERS,
        json={"stage": "editorial", "approve": True},
    )
    client.post(
        f"{base}/{item_id}/revisions/{revision_id}/decision",
        headers=HEADERS,
        json={"stage": "client", "approve": True},
    )

    publish = client.post(
        f"{base}/{item_id}/revisions/{revision_id}/publish",
        headers=HEADERS,
        json={
            "publishing_target_id": str(uuid4()),
            "workflow_run_id": str(ids["workflow_run"]),
            "target_path": "src/content/blog/untargeted-post.md",
            "idempotency_key": "content-publish-missing-target",
        },
    )
    assert publish.status_code == 409


@pytest.mark.integration
def test_cross_tenant_item_detail_is_not_found(
    content_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = content_client
    other_org = ids["other_organization"]
    response = client.get(f"/api/v1/organizations/{other_org}/content/{uuid4()}", headers=HEADERS)
    assert response.status_code in (403, 404)


@pytest.mark.integration
def test_operator_can_configure_github_connection_and_publishing_target_in_app(
    content_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    """A production operator can configure a GitHub publishing target through the
    application API — no manual SQL. The GitHub access token (external credential)
    is registered as a connection, then a target is configured referencing it.
    """
    client, ids = content_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/content"

    connections = client.get(f"{base}/connections", headers=HEADERS)
    assert connections.status_code == 200
    pre_count = len(connections.json()["data"])

    connection = client.post(
        f"{base}/connections",
        headers=HEADERS,
        json={
            "access_token": "ghp_external-credential-token",
            "external_account_reference": "org/site-repo-content",
        },
    )
    assert connection.status_code == 201, connection.text
    assert connection.json()["data"]["status"] == "connected"
    connection_id = connection.json()["data"]["id"]

    listed = client.get(f"{base}/connections", headers=HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == pre_count + 1

    target = client.post(
        f"{base}/targets",
        headers=HEADERS,
        json={
            "key": "secondary",
            "connection_id": connection_id,
            "target_type": "github_astro",
            "repository_id": "org/site-repo-content",
            "base_branch": "main",
            "allowed_path_prefix": "src/content",
        },
    )
    assert target.status_code == 201, target.text
    assert target.json()["data"]["status"] == "active"
    assert target.json()["data"]["repository_id"] == "org/site-repo-content"
    assert target.json()["data"]["base_branch"] == "main"

    targets = client.get(f"{base}/targets", headers=HEADERS)
    assert targets.status_code == 200
    configured = [t for t in targets.json()["data"] if t["key"] == "secondary"]
    assert any(t["repository_id"] == "org/site-repo-content" for t in configured)


@pytest.mark.integration
def test_create_target_with_unconnected_connection_is_rejected(
    content_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    """A target referencing a missing connection is rejected, not silently stored."""
    client, ids = content_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/content"

    response = client.post(
        f"{base}/targets",
        headers=HEADERS,
        json={
            "key": "orphan",
            "connection_id": str(uuid4()),
            "target_type": "github_astro",
            "repository_id": "org/repo",
            "base_branch": "main",
            "allowed_path_prefix": "src/content",
        },
    )
    assert response.status_code == 409
