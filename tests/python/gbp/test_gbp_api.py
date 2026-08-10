"""Production-capable GBP route, audit, and tenant-isolation tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.main import create_app
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation, GBPProfileSnapshot


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
        key_id="gbp-test-key",
    )


@pytest.fixture
def gbp_client(
    postgresql_test_url: str,
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with gbp_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="gbp-api-catalog")
            organization = Organization(
                name="GBP Test Org",
                slug="gbp-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="GBP Other Org",
                slug="gbp-other-org",
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
            other_location = Location(
                organization_id=other_organization.id,
                name="Other Downtown",
                slug="other-downtown",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=True,
                version=1,
            )
            session.add_all([location, other_location])
            await session.flush()

            membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="gbp-api-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="gbp-api-owner",
            )

            provider = Provider(
                key="google_business_profile",
                name="Google Business Profile",
                status="active",
                capabilities=["profile.read", "profile.write"],
            )
            session.add(provider)
            await session.flush()

            connection = IntegrationConnection(
                organization_id=organization.id,
                provider_id=provider.id,
                external_account_reference="accounts/123",
                status="connected",
            )
            session.add(connection)
            await session.flush()

            gbp_account = GBPAccount(
                organization_id=organization.id,
                connection_id=connection.id,
                external_account_id="accounts/123",
                display_name="Example Business",
                status="discovered",
            )
            session.add(gbp_account)
            await session.flush()

            gbp_location = GBPLocation(
                organization_id=organization.id,
                connection_id=gbp_account.connection_id,
                account_id=gbp_account.id,
                external_location_id="locations/456",
                business_name="Example Business - Downtown",
                mapping_status="unmapped",
            )
            session.add(gbp_location)
            await session.flush()

            snapshot = GBPProfileSnapshot(
                organization_id=organization.id,
                gbp_location_id=gbp_location.id,
                normalized_profile={"title": "Example Business", "storefrontAddress": {}},
                content_hash="deterministic-hash",
                completeness="full",
                observed_at=datetime.now(UTC),
            )
            session.add(snapshot)
            await session.flush()

            workflow_definition = WorkflowDefinition(
                key="gbp.publish_change", name="Publish GBP change", owner="gbp"
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
                product_key="gbp",
                trigger_type="manual",
                idempotency_key="gbp-test-workflow-run-001",
                request_hash="deterministic-request-hash",
                input_document={},
                correlation_id="gbp-test-workflow",
            )
            session.add(workflow_run)
            await session.flush()

            identifiers = {
                "workflow_run": workflow_run.id,
                "organization": organization.id,
                "other_organization": other_organization.id,
                "location": location.id,
                "other_location": other_location.id,
                "assigned_subject": profile.auth_user_id,
                "gbp_account": gbp_account.id,
                "gbp_location": gbp_location.id,
                "snapshot": snapshot.id,
            }
            return claims(profile.auth_user_id), identifiers

    verified, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(verified)
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, identifiers


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.mark.integration
def test_organization_scoped_discovery_lists_are_real_and_tenant_isolated(
    gbp_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = gbp_client
    org = ids["organization"]

    accounts = client.get(f"/api/v1/organizations/{org}/gbp/accounts", headers=HEADERS)
    assert accounts.status_code == 200
    assert accounts.headers["Cache-Control"] == "no-store"
    assert [item["id"] for item in accounts.json()["data"]] == [str(ids["gbp_account"])]

    locations = client.get(f"/api/v1/organizations/{org}/gbp/locations", headers=HEADERS)
    assert locations.status_code == 200
    body = locations.json()["data"]
    assert [item["id"] for item in body] == [str(ids["gbp_location"])]
    assert body[0]["mapping_status"] == "unmapped"

    other_org = ids["other_organization"]
    cross_tenant = client.get(f"/api/v1/organizations/{other_org}/gbp/accounts", headers=HEADERS)
    assert cross_tenant.status_code == 403


@pytest.mark.integration
def test_full_vertical_slice_flow_produces_readable_audit_history(
    gbp_client: tuple[TestClient, dict[str, UUID]],
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = gbp_client
    org, location, gbp_location = ids["organization"], ids["location"], ids["gbp_location"]
    base = f"/api/v1/organizations/{org}/locations/{location}/gbp"

    confirm = client.post(
        f"{base}/locations/{gbp_location}/confirm",
        headers=HEADERS,
        json={"location_id": str(location), "write_enabled": True},
    )
    assert confirm.status_code == 200
    assert confirm.json()["data"]["mapping_status"] == "confirmed"

    async def confirmed_mapping() -> tuple[ProviderResourceMapping, GBPLocation]:
        async with gbp_session_factory() as session:
            mapping = await session.scalar(
                select(ProviderResourceMapping).where(
                    ProviderResourceMapping.organization_id == org,
                    ProviderResourceMapping.platform_resource_id == location,
                    ProviderResourceMapping.resource_type == "location",
                )
            )
            gbp = await session.get(GBPLocation, gbp_location)
            assert mapping is not None
            assert gbp is not None
            return mapping, gbp

    resource_mapping, confirmed_location = asyncio.run(confirmed_mapping())
    assert resource_mapping.external_resource_id == "locations/456"
    assert resource_mapping.status == "active"
    assert confirmed_location.integration_resource_id == resource_mapping.id

    location_audit = client.get(f"{base}/locations/{gbp_location}/audit", headers=HEADERS)
    assert location_audit.status_code == 200
    assert location_audit.json()["data"][0]["event_type"] == "gbp.location.mapping_confirmed"

    propose = client.post(
        f"{base}/locations/{gbp_location}/changes",
        headers=HEADERS,
        json={
            "base_snapshot_id": str(ids["snapshot"]),
            "desired_fields": {"profile.description": "Updated description"},
            "approved_fact_revision_ids": [str(uuid4())],
        },
    )
    assert propose.status_code == 201
    revision_id = propose.json()["data"]["id"]

    get_change = client.get(f"{base}/changes/{revision_id}", headers=HEADERS)
    assert get_change.status_code == 200
    assert get_change.json()["data"]["status"] == "awaiting_approval"

    decide = client.post(
        f"{base}/changes/{revision_id}/decision",
        headers=HEADERS,
        json={"decision": "approve"},
    )
    assert decide.status_code == 200
    assert decide.json()["data"]["status"] == "approved"

    change_audit = client.get(f"{base}/changes/{revision_id}/audit", headers=HEADERS)
    assert change_audit.status_code == 200
    events = {item["event_type"] for item in change_audit.json()["data"]}
    assert events == {"gbp.change.proposed", "gbp.change.approved"}

    publish = client.post(
        f"{base}/changes/{revision_id}/publish",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "idempotency_key": "gbp-publish-key-001",
        },
    )
    assert publish.status_code == 202
    assert publish.json()["data"]["status"] == "reserved"
    publication_id = publish.json()["data"]["publication_id"]

    publications = client.get(f"{base}/publications", headers=HEADERS)
    assert publications.status_code == 200
    assert [item["id"] for item in publications.json()["data"]] == [publication_id]

    publication_audit = client.get(f"{base}/publications/{publication_id}/audit", headers=HEADERS)
    assert publication_audit.status_code == 200
    assert publication_audit.json()["data"][0]["event_type"] == "gbp.publication.reserved"


@pytest.mark.integration
def test_cross_tenant_change_and_publication_audit_are_not_found(
    gbp_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = gbp_client
    org, other_location = ids["organization"], ids["other_location"]
    base = f"/api/v1/organizations/{org}/locations/{other_location}/gbp"

    missing_change = client.get(f"{base}/changes/{uuid4()}", headers=HEADERS)
    assert missing_change.status_code in (403, 404)

    missing_publication_audit = client.get(f"{base}/publications/{uuid4()}/audit", headers=HEADERS)
    assert missing_publication_audit.status_code in (403, 404)
