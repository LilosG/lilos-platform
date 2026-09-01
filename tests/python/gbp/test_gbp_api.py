"""Production-capable GBP route, audit, and tenant-isolation tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from authorization.fixtures import add_effective_product_entitlement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.audit.models import AuditEvent
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
) -> Generator[tuple[TestClient, dict[str, UUID], FakeVerifier], None, None]:
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
            await add_effective_product_entitlement(
                session,
                organization.id,
                "gbp",
                correlation_id="gbp-api-entitlement",
            )

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
        yield client, identifiers, verifier


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.mark.integration
def test_organization_scoped_discovery_lists_are_real_and_tenant_isolated(
    gbp_client: tuple[TestClient, dict[str, UUID], FakeVerifier],
) -> None:
    client, ids, _verifier = gbp_client
    org = ids["organization"]

    accounts = client.get(f"/api/v1/organizations/{org}/gbp/accounts", headers=HEADERS)
    # organization_owner has gbp.connect (all permissions).  Account discovery
    # requires the privileged gbp.connect permission, which the owner role
    # legitimately holds.
    assert accounts.status_code == 200

    locations = client.get(f"/api/v1/organizations/{org}/gbp/locations", headers=HEADERS)
    assert locations.status_code == 200
    body = locations.json()["data"]
    # The gbp.read product path defaults to confirmed-only.  The seeded
    # location is unmapped, so the list is empty until it is confirmed.
    assert body == []

    other_org = ids["other_organization"]
    cross_tenant = client.get(f"/api/v1/organizations/{other_org}/gbp/accounts", headers=HEADERS)
    assert cross_tenant.status_code == 403


@pytest.mark.integration
def test_remove_mapping_retires_only_selected_gbp_and_preserves_google_resource(
    gbp_client: tuple[TestClient, dict[str, UUID], FakeVerifier],
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids, _verifier = gbp_client
    org, platform_location = ids["organization"], ids["location"]

    async def add_correct_location() -> UUID:
        async with gbp_session_factory.begin() as session:
            wrong = await session.get(GBPLocation, ids["gbp_location"])
            assert wrong is not None
            correct = GBPLocation(
                organization_id=org,
                connection_id=wrong.connection_id,
                account_id=wrong.account_id,
                external_location_id="locations/coco-maya",
                business_name="Coco Maya by Miss B's",
                mapping_status="unmapped",
            )
            session.add(correct)
            await session.flush()
            return correct.id

    correct_id = asyncio.run(add_correct_location())
    base = f"/api/v1/organizations/{org}/locations/{platform_location}/gbp"
    for gbp_location_id, write_enabled in (
        (ids["gbp_location"], False),
        (correct_id, True),
    ):
        response = client.post(
            f"{base}/locations/{gbp_location_id}/confirm",
            headers=HEADERS,
            json={"location_id": str(platform_location), "write_enabled": write_enabled},
        )
        assert response.status_code == 200

    removed = client.delete(
        f"{base}/locations/{ids['gbp_location']}/mapping",
        headers=HEADERS,
    )
    assert removed.status_code == 200
    assert removed.json()["data"] == {
        "id": str(ids["gbp_location"]),
        "mapping_status": "unmapped",
        "write_enabled": False,
    }

    product_locations = client.get(f"/api/v1/organizations/{org}/gbp/locations", headers=HEADERS)
    assert product_locations.status_code == 200
    assert [item["business_name"] for item in product_locations.json()["data"]] == [
        "Coco Maya by Miss B's"
    ]

    async def mapping_state() -> tuple[
        GBPLocation, GBPLocation, list[ProviderResourceMapping], str
    ]:
        async with gbp_session_factory() as session:
            wrong = await session.get(GBPLocation, ids["gbp_location"])
            correct = await session.get(GBPLocation, correct_id)
            mappings = list(
                await session.scalars(
                    select(ProviderResourceMapping)
                    .where(ProviderResourceMapping.organization_id == org)
                    .order_by(ProviderResourceMapping.external_resource_id)
                )
            )
            audit_event = await session.scalar(
                select(AuditEvent)
                .where(
                    AuditEvent.organization_id == org,
                    AuditEvent.resource_type == "gbp_location",
                    AuditEvent.resource_id == ids["gbp_location"],
                    AuditEvent.event_type == "gbp.location.mapping_removed",
                )
                .order_by(AuditEvent.occurred_at.desc())
            )
            assert wrong is not None
            assert correct is not None
            assert audit_event is not None
            return wrong, correct, mappings, audit_event.event_type

    wrong, correct, mappings, event_type = asyncio.run(mapping_state())
    mapping_by_external = {item.external_resource_id: item for item in mappings}
    assert wrong.mapping_status == "unmapped"
    assert wrong.location_id is None
    assert wrong.integration_resource_id is None
    assert wrong.write_enabled is False
    assert mapping_by_external["locations/456"].status == "stale"
    assert mapping_by_external["locations/456"].platform_resource_id is None
    assert correct.mapping_status == "confirmed"
    assert correct.location_id == platform_location
    assert correct.write_enabled is True
    assert mapping_by_external["locations/coco-maya"].status == "active"
    assert mapping_by_external["locations/coco-maya"].platform_resource_id == platform_location
    assert event_type == "gbp.location.mapping_removed"


@pytest.mark.integration
def test_full_vertical_slice_flow_produces_readable_audit_history(
    gbp_client: tuple[TestClient, dict[str, UUID], FakeVerifier],
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids, _verifier = gbp_client
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
    gbp_client: tuple[TestClient, dict[str, UUID], FakeVerifier],
) -> None:
    client, ids, _verifier = gbp_client
    org, other_location = ids["organization"], ids["other_location"]
    base = f"/api/v1/organizations/{org}/locations/{other_location}/gbp"

    missing_change = client.get(f"{base}/changes/{uuid4()}", headers=HEADERS)
    assert missing_change.status_code in (403, 404)

    missing_publication_audit = client.get(f"{base}/publications/{uuid4()}/audit", headers=HEADERS)
    assert missing_publication_audit.status_code in (403, 404)


@pytest.mark.integration
def test_gbp_read_product_path_returns_only_confirmed_mapped_locations(
    gbp_client: tuple[TestClient, dict[str, UUID], FakeVerifier],
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """gbp.read must not leak unmapped provider-discovered resources.

    The product read path (GET …/gbp/locations with gbp.read) defaults to
    mapping_status='confirmed'.  An ordinary client/product reader cannot
    enumerate unmapped provider resources through this endpoint.  Unmapped
    discovery remains available through the privileged integration discovery
    path (POST /integrations/google/discover with gbp.connect).
    """
    client, ids, _verifier = gbp_client
    org = ids["organization"]
    location = ids["location"]
    gbp_location = ids["gbp_location"]

    base = f"/api/v1/organizations/{org}/locations/{location}/gbp"
    org_locations_url = f"/api/v1/organizations/{org}/gbp/locations"

    # (a) Before confirmation: product read path returns empty.
    locations = client.get(org_locations_url, headers=HEADERS)
    assert locations.status_code == 200
    assert locations.json()["data"] == []

    # (b) Confirm the mapping — the product read path should now include it.
    confirm = client.post(
        f"{base}/locations/{gbp_location}/confirm",
        headers=HEADERS,
        json={"location_id": str(location), "write_enabled": True},
    )
    assert confirm.status_code == 200
    assert confirm.json()["data"]["mapping_status"] == "confirmed"

    locations = client.get(org_locations_url, headers=HEADERS)
    assert locations.status_code == 200
    body = locations.json()["data"]
    assert len(body) == 1
    assert body[0]["id"] == str(gbp_location)
    assert body[0]["mapping_status"] == "confirmed"
    assert body[0]["business_name"] == "Example Business - Downtown"

    # (c) Cross-tenant isolation: a different org cannot see this location.
    other_org = ids["other_organization"]
    cross_tenant = client.get(f"/api/v1/organizations/{other_org}/gbp/locations", headers=HEADERS)
    assert cross_tenant.status_code == 403


@pytest.mark.integration
def test_confirm_mapping_preserves_aal2_route_requirement(
    gbp_client: tuple[TestClient, dict[str, UUID], FakeVerifier],
) -> None:
    client, ids, verifier = gbp_client
    verifier.result = claims(ids["assigned_subject"], assurance=AssuranceLevel.AAL1)

    response = client.post(
        (
            f"/api/v1/organizations/{ids['organization']}"
            f"/locations/{ids['location']}/gbp/locations/{ids['gbp_location']}/confirm"
        ),
        headers=HEADERS,
        json={"location_id": str(ids["location"]), "write_enabled": True},
    )

    assert response.status_code == 403
    # Confirming a mapping is an AAL2 route, so an AAL1 member is refused for
    # assurance rather than permission and is told which: the client can prompt a
    # step-up instead of showing "you do not have permission".
    assert response.json()["error"]["code"] == "STEP_UP_REQUIRED"

    remove = client.delete(
        (
            f"/api/v1/organizations/{ids['organization']}"
            f"/locations/{ids['location']}/gbp/locations/{ids['gbp_location']}/mapping"
        ),
        headers=HEADERS,
    )
    assert remove.status_code == 403
    assert remove.json()["error"]["code"] == "STEP_UP_REQUIRED"


@pytest.mark.integration
def test_write_access_transitions_are_persisted_and_audited_truthfully(
    gbp_client: tuple[TestClient, dict[str, UUID], FakeVerifier],
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids, _verifier = gbp_client
    base = (
        f"/api/v1/organizations/{ids['organization']}"
        f"/locations/{ids['location']}/gbp/locations/{ids['gbp_location']}/confirm"
    )

    initial = client.post(
        base,
        headers=HEADERS,
        json={"location_id": str(ids["location"])},
    )
    assert initial.status_code == 200
    assert initial.json()["data"]["write_enabled"] is False

    enabled = client.post(
        base,
        headers=HEADERS,
        json={"location_id": str(ids["location"]), "write_enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["data"]["write_enabled"] is True

    disabled = client.post(
        base,
        headers=HEADERS,
        json={"location_id": str(ids["location"]), "write_enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["write_enabled"] is False

    idempotent = client.post(
        base,
        headers=HEADERS,
        json={"location_id": str(ids["location"]), "write_enabled": False},
    )
    assert idempotent.status_code == 200

    async def assert_persistence_and_audit() -> None:
        async with gbp_session_factory() as session:
            location = await session.get(GBPLocation, ids["gbp_location"])
            assert location is not None
            assert location.write_enabled is False

            events = list(
                await session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.organization_id == ids["organization"],
                        AuditEvent.resource_type == "gbp_location",
                        AuditEvent.resource_id == ids["gbp_location"],
                    )
                )
            )
            write_access_events = [
                event for event in events if event.event_type == "gbp.location.write_access_changed"
            ]
            assert len(write_access_events) == 2
            transitions = {
                (
                    event.event_metadata["previous_write_enabled"],
                    event.event_metadata["new_write_enabled"],
                )
                for event in write_access_events
            }
            assert transitions == {(False, True), (True, False)}
            for event in write_access_events:
                assert event.event_metadata["previous_location_id"] == str(ids["location"])
                assert event.event_metadata["new_location_id"] == str(ids["location"])
                assert event.event_metadata["previous_mapping_status"] == "confirmed"
                assert event.event_metadata["new_mapping_status"] == "confirmed"

    asyncio.run(assert_persistence_and_audit())


@pytest.mark.integration
def test_google_unmapped_uses_platform_location_identity_and_reconciles_workspace(
    gbp_client: tuple[TestClient, dict[str, UUID], FakeVerifier],
) -> None:
    client, ids, _verifier = gbp_client
    integrations_base = f"/api/v1/organizations/{ids['organization']}/integrations/google"

    before = client.get(f"{integrations_base}/unmapped", headers=HEADERS)
    assert before.status_code == 200
    assert [item["id"] for item in before.json()["data"]] == [str(ids["gbp_location"])]

    confirm = client.post(
        (
            f"/api/v1/organizations/{ids['organization']}"
            f"/locations/{ids['location']}/gbp/locations/{ids['gbp_location']}/confirm"
        ),
        headers=HEADERS,
        json={"location_id": str(ids["location"])},
    )
    assert confirm.status_code == 200
    assert confirm.json()["data"]["write_enabled"] is False

    after = client.get(f"{integrations_base}/unmapped", headers=HEADERS)
    assert after.status_code == 200
    assert after.json()["data"] == []

    workspace = client.get(f"{integrations_base}/workspace", headers=HEADERS)
    assert workspace.status_code == 200
    mapped = workspace.json()["data"]["mapped_resources"]
    assert len(mapped) == 1
    assert mapped[0]["platform_resource_id"] == str(ids["location"])
    assert mapped[0]["gbp_location_id"] == str(ids["gbp_location"])
    assert mapped[0]["mapping_status"] == "confirmed"
    assert mapped[0]["write_enabled"] is False
