"""Production-capable Reviews route, audit, notification, and isolation tests."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from authorization.fixtures import add_effective_product_entitlement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.main import create_app
from apps.api.app.notifications.models import NotificationEvent
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision, ReviewRevision
from apps.api.app.products.reviews.service import ReviewService


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
        key_id="reviews-test-key",
    )


def run_db[T](postgresql_test_url: str, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Run one unit of DB work against a fresh, short-lived engine.

    Each call gets its own engine bound to the event loop `asyncio.run` creates
    for this call, then disposes it before returning. This avoids reusing
    asyncpg connections across separate event loops, which breaks connection
    cleanup independent of the code under test.
    """

    async def scenario() -> T:
        engine = create_async_engine(postgresql_test_url)
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.fixture
def reviews_client(
    postgresql_test_url: str,
    reviews_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with reviews_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="reviews-api-catalog")
            organization = Organization(
                name="Reviews Test Org",
                slug="reviews-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="Reviews Other Org",
                slug="reviews-other-org",
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
                "reviews",
                correlation_id="reviews-api-entitlement",
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
            sibling_location = Location(
                organization_id=organization.id,
                name="Uptown",
                slug="uptown",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://uptown.example.invalid",
                is_primary=False,
                version=1,
            )
            session.add_all([location, sibling_location])
            await session.flush()

            membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="reviews-api-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="reviews-api-owner",
            )

            provider = Provider(
                key="google_business_profile",
                name="Google Business Profile",
                status="active",
                capabilities=["reviews.read"],
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
            resource_mapping = ProviderResourceMapping(
                organization_id=organization.id,
                connection_id=connection.id,
                resource_type="gbp_location",
                external_resource_id="locations/456",
                platform_resource_id=location.id,
                status="active",
            )
            session.add(resource_mapping)
            await session.flush()

            identifiers = {
                "organization": organization.id,
                "other_organization": other_organization.id,
                "location": location.id,
                "sibling_location": sibling_location.id,
                "assigned_subject": profile.auth_user_id,
                "integration_resource": resource_mapping.id,
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


def _ingest(
    postgresql_test_url: str,
    ids: dict[str, UUID],
    *,
    body: str,
    rating: float,
    external_id: str,
) -> None:
    async def work(session: AsyncSession) -> None:
        async with session.begin():
            await ReviewService().ingest(
                session,
                organization_id=ids["organization"],
                location_id=ids["location"],
                integration_resource_id=ids["integration_resource"],
                external_review_id=external_id,
                provider="google_business_profile",
                rating=rating,
                title=None,
                body=body,
                created_at=datetime.now(UTC),
                updated_at=None,
                correlation_id="reviews-test-ingest",
            )

    run_db(postgresql_test_url, work)


def _fetch_review_and_revision(
    postgresql_test_url: str, organization_id: UUID, location_id: UUID
) -> tuple[UUID, UUID]:
    async def work(session: AsyncSession) -> tuple[UUID, UUID]:
        review = (
            await session.scalars(
                select(Review).where(
                    Review.organization_id == organization_id, Review.location_id == location_id
                )
            )
        ).one()
        revision = (
            await session.scalars(
                select(ReviewRevision).where(ReviewRevision.review_id == review.id)
            )
        ).one()
        return review.id, revision.id

    return run_db(postgresql_test_url, work)


def _notification_event_exists(
    postgresql_test_url: str, organization_id: UUID, event_type: str
) -> bool:
    async def work(session: AsyncSession) -> bool:
        return (
            await session.scalar(
                select(NotificationEvent).where(
                    NotificationEvent.organization_id == organization_id,
                    NotificationEvent.event_type == event_type,
                )
            )
        ) is not None

    return run_db(postgresql_test_url, work)


@pytest.mark.integration
def test_ingest_classifies_and_lists_with_filters_search_and_pagination(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]

    _ingest(
        postgresql_test_url,
        ids,
        body="Great service, very happy",
        rating=5,
        external_id="review-1",
    )
    _ingest(
        postgresql_test_url,
        ids,
        body="An employee assaulted me and I need a refund",
        rating=1,
        external_id="review-2",
    )

    base = f"/api/v1/organizations/{org}/locations/{location}/reviews"
    listing = client.get(base, headers=HEADERS)
    assert listing.status_code == 200
    assert listing.headers["Cache-Control"] == "no-store"
    assert len(listing.json()["data"]) == 2
    assert listing.json()["pagination"]["limit"] == 50
    assert all(item["last_synced_at"] for item in listing.json()["data"])

    restricted = [item for item in listing.json()["data"] if item["risk_level"] == "high"]
    assert len(restricted) == 1
    assert restricted[0]["status"] == "escalated"

    filtered = client.get(f"{base}?status_filter=escalated", headers=HEADERS)
    assert filtered.status_code == 200
    assert len(filtered.json()["data"]) == 1

    searched = client.get(f"{base}?search=assaulted", headers=HEADERS)
    assert searched.status_code == 200
    assert len(searched.json()["data"]) == 1

    paged = client.get(f"{base}?limit=1&offset=0", headers=HEADERS)
    assert paged.status_code == 200
    assert len(paged.json()["data"]) == 1
    assert paged.json()["pagination"]["has_more"] is True

    summary = client.get(f"{base}/summary", headers=HEADERS)
    assert summary.status_code == 200
    assert summary.json()["data"]["open_restricted_cases"] == 1


@pytest.mark.integration
def test_manual_and_ai_draft_full_flow_produces_audit_and_notification(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]

    _ingest(
        postgresql_test_url,
        ids,
        body="Good experience overall",
        rating=4,
        external_id="review-manual",
    )
    review_id, revision_id = _fetch_review_and_revision(postgresql_test_url, org, location)
    base = f"/api/v1/organizations/{org}/locations/{location}/reviews"

    detail = client.get(f"{base}/{review_id}", headers=HEADERS)
    assert detail.status_code == 200
    assert len(detail.json()["data"]["revisions"]) == 1

    _approved_fact(client, org)
    manual = client.post(
        f"{base}/{review_id}/responses",
        headers=HEADERS,
        json={
            "review_revision_id": str(revision_id),
            "response_text": "Thank you so much for your kind words!",
            "generated_by_type": "user",
        },
    )
    assert manual.status_code == 201
    manual_response_id = manual.json()["data"]["id"]

    response_audit = client.get(f"{base}/responses/{manual_response_id}/audit", headers=HEADERS)
    assert response_audit.status_code == 200
    assert response_audit.json()["data"][0]["event_type"] == "reviews.response.drafted"

    review_audit = client.get(f"{base}/{review_id}/audit", headers=HEADERS)
    assert review_audit.status_code == 200
    assert review_audit.json()["data"][0]["event_type"] == "reviews.review.ingested"

    # Create a real approved business fact for AI grounding
    fact_propose = client.post(
        f"/api/v1/organizations/{org}/business-facts",
        headers=HEADERS,
        json={
            "fact_key": "business.name",
            "value": "Test Business",
            "value_type": "string",
            "source": "organization_profile",
            "authority": "system_derived",
            "change_reason": "Test fact for reviews AI grounding",
        },
    )
    assert fact_propose.status_code == 201
    fact_revision_id = fact_propose.json()["data"]["id"]

    fact_approve = client.post(
        f"/api/v1/organizations/{org}/business-facts/{fact_revision_id}/decision",
        headers=HEADERS,
        json={"decision": "approve"},
    )
    assert fact_approve.status_code == 200

    ai = client.post(
        f"{base}/{review_id}/responses/ai-draft",
        headers=HEADERS,
        json={
            "review_revision_id": str(revision_id),
            "idempotency_key": "reviews-ai-draft-key-001",
        },
    )
    assert ai.status_code == 201
    assert ai.json()["data"]["requires_human_review"] is True
    assert ai.json()["data"]["response_text"]
    ai_response_id = ai.json()["data"]["id"]

    sibling_base = f"/api/v1/organizations/{org}/locations/{ids['sibling_location']}/reviews"
    wrong_location_audit = client.get(
        f"{sibling_base}/responses/{ai_response_id}/audit", headers=HEADERS
    )
    assert wrong_location_audit.status_code == 404
    wrong_location_approve = client.post(
        f"{sibling_base}/{review_id}/responses/{ai_response_id}/approve", headers=HEADERS
    )
    assert wrong_location_approve.status_code == 404

    approve = client.post(f"{base}/{review_id}/responses/{ai_response_id}/approve", headers=HEADERS)
    assert approve.status_code == 200
    assert approve.json()["data"]["status"] == "approved"

    publish = client.post(
        f"{base}/{review_id}/responses/{ai_response_id}/publish",
        headers=HEADERS,
        json={"idempotency_key": "reviews-publish-key-001"},
    )
    assert publish.status_code == 202
    assert publish.json()["data"]["status"] == "publishing"

    responses = client.get(f"{base}/{review_id}/responses", headers=HEADERS)
    assert responses.status_code == 200
    statuses = {item["id"]: item["status"] for item in responses.json()["data"]}
    assert statuses[ai_response_id] == "publishing"

    assert (
        _notification_event_exists(
            postgresql_test_url, org, "reviews.response.publication_reserved"
        )
        is True
    )


def _response_fact_ids(postgresql_test_url: str, response_id: str) -> list[str]:
    async def work(session: AsyncSession) -> list[str]:
        row = await session.get(ReviewResponseRevision, UUID(response_id))
        assert row is not None
        return [str(x) for x in row.approved_fact_revision_ids]

    return run_db(postgresql_test_url, work)


@pytest.mark.integration
def test_replies_resolve_approved_facts_on_the_server(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]
    _ingest(postgresql_test_url, ids, body="Lovely evening", rating=5, external_id="review-facts")
    review_id, revision_id = _fetch_review_and_revision(postgresql_test_url, org, location)
    base = f"/api/v1/organizations/{org}/locations/{location}/reviews/{review_id}/responses"

    # No approved facts: a typed code, no prose to match.
    for path, payload in (
        ("/ai-draft", {"idempotency_key": "reviews-nofacts-key-1"}),
        ("", {"response_text": "Thank you!", "generated_by_type": "user"}),
    ):
        refused = client.post(
            base + path,
            headers=HEADERS,
            json={"review_revision_id": str(revision_id), **payload},
        )
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "REVIEW_DRAFT_GROUNDING_REQUIRED"

    fact_id = _approved_fact(client, org)
    ai = client.post(
        base + "/ai-draft",
        headers=HEADERS,
        json={"review_revision_id": str(revision_id), "idempotency_key": "reviews-facts-key-01"},
    )
    assert ai.status_code == 201
    assert _response_fact_ids(postgresql_test_url, ai.json()["data"]["id"]) == [fact_id]

    manual = client.post(
        base,
        headers=HEADERS,
        json={
            "review_revision_id": str(revision_id),
            "response_text": "Thank you for coming in.",
            "generated_by_type": "user",
        },
    )
    assert manual.status_code == 201
    assert _response_fact_ids(postgresql_test_url, manual.json()["data"]["id"]) == [fact_id]


@pytest.mark.integration
def test_restricted_review_cannot_auto_publish_and_generates_notification(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]

    _ingest(
        postgresql_test_url,
        ids,
        body="I was injured and need a lawyer",
        rating=1,
        external_id="review-restricted",
    )
    review_id, revision_id = _fetch_review_and_revision(postgresql_test_url, org, location)
    base = f"/api/v1/organizations/{org}/locations/{location}/reviews"

    draft = client.post(
        f"{base}/{review_id}/responses",
        headers=HEADERS,
        json={
            "review_revision_id": str(revision_id),
            "response_text": "We are so sorry to hear this and want to help.",
            "generated_by_type": "user",
            "approved_fact_revision_ids": [_approved_fact(client, org)],
        },
    )
    response_id = draft.json()["data"]["id"]
    client.post(f"{base}/{review_id}/responses/{response_id}/approve", headers=HEADERS)
    publish = client.post(
        f"{base}/{review_id}/responses/{response_id}/publish",
        headers=HEADERS,
        json={"idempotency_key": "reviews-restricted-publish-key"},
    )
    assert publish.status_code == 409

    assert (
        _notification_event_exists(postgresql_test_url, org, "reviews.restricted_case_created")
        is True
    )


@pytest.mark.integration
def test_cross_tenant_review_detail_is_not_found(
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = reviews_client
    other_org, location = ids["other_organization"], ids["location"]
    base = f"/api/v1/organizations/{other_org}/locations/{location}/reviews"
    response = client.get(f"{base}/{uuid4()}", headers=HEADERS)
    assert response.status_code in (403, 404)


@pytest.mark.integration
def test_ingest_route_maps_to_ingest_handler_not_get_review_by_id(
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    """Regression: the production frontend sends ``POST .../reviews/ingest``.

    Production returned ``405 Method Not Allowed`` because an older API build
    lacked the ``POST /ingest`` route, so the path matched ``GET .../reviews/{review_id}``
    (``review_id == "ingest"``) with the wrong method. This test proves the current
    route table maps the exact frontend-shaped request to the ``ingest_reviews``
    handler: an authenticated POST with body ``{}`` must NOT return 405, and with
    no active GBP location mapping it returns a truthful 409 the operator can act on.
    """
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]
    base = f"/api/v1/organizations/{org}/locations/{location}/reviews"

    response = client.post(f"{base}/ingest", headers=HEADERS, json={})

    assert response.status_code != 405, "ingest route is shadowed by GET /{review_id}"
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "REVIEW_INGESTION_UNAVAILABLE"
    assert "Google Business Profile" in body["error"]["message"]


def _approved_fact(client: TestClient, org: UUID) -> str:
    result = client.post(
        f"/api/v1/organizations/{org}/business-facts",
        headers=HEADERS,
        json={
            "fact_key": "business.name",
            "value": "Synthetic Reviews Business",
            "value_type": "string",
            "source": "organization_profile",
            "authority": "system_derived",
            "change_reason": "Reviews test grounding",
        },
    )
    assert result.status_code == 201
    fact_id = result.json()["data"]["id"]
    assert (
        client.post(
            f"/api/v1/organizations/{org}/business-facts/{fact_id}/decision",
            headers=HEADERS,
            json={"decision": "approve"},
        ).status_code
        == 200
    )
    return str(fact_id)


def test_command_center_reviews_missing_zero_scoping_and_private(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]
    path = f"/api/v1/organizations/{org}/command-center/reviews"
    missing = client.get(path, headers=HEADERS, params={"location_id": str(location)})
    assert missing.status_code == 200
    assert missing.headers["Cache-Control"] == "private, no-store"
    assert missing.json()["inventory_count"] is None
    assert missing.json()["average_rating"] is None
    assert missing.json()["items"] == []
    assert missing.json()["campaigns"] == "unavailable_no_canonical_source"
    assert client.get(path).status_code == 401
    assert (
        client.get(path, headers=HEADERS, params={"location_id": str(uuid4())}).status_code == 404
    )
    assert (
        client.get(
            f"/api/v1/organizations/{ids['other_organization']}/command-center/reviews",
            headers=HEADERS,
        ).status_code
        == 404
    )
    # A completed empty ingestion is real evidence; absent source is not zero.
    from apps.api.app.routes.reviews import service

    async def completed(session: AsyncSession) -> None:
        async with session.begin():
            await service._audit(
                session,
                event="reviews.ingest.completed",
                organization_id=org,
                location_id=location,
                actor_id=None,
                resource_type="location",
                resource_id=location,
                correlation_id="phase3-empty",
                summary="Empty synthetic import",
                metadata={"total": 0},
            )

    run_db(postgresql_test_url, completed)
    zero = client.get(path, headers=HEADERS, params={"location_id": str(location)}).json()
    assert zero["inventory_count"] == 0
    assert zero["average_rating"] is None
    assert zero["source"]["freshness"] == "fresh"
    assert zero["source"]["quality"] == "partial"


def test_command_center_reviews_exact_revision_dispatch_and_audit(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]
    _ingest(postgresql_test_url, ids, body="Good visit", rating=5, external_id="phase3-review")
    review, revision = _fetch_review_and_revision(postgresql_test_url, org, location)
    base = f"/api/v1/organizations/{org}/locations/{location}/reviews/{review}/responses"
    payload = {
        "review_revision_id": str(revision),
        "response_text": "Thank you for visiting.",
        "generated_by_type": "user",
        "approved_fact_revision_ids": [_approved_fact(client, org)],
    }
    draft = client.post(base, headers=HEADERS, json=payload)
    assert draft.status_code == 201
    response_id = draft.json()["data"]["id"]
    projection = f"/api/v1/organizations/{org}/command-center/reviews/locations/{location}/{review}"
    view = client.get(projection, headers=HEADERS).json()
    assert view["can_draft"] is True
    response = view["responses"][0]
    assert response["approval_required"] is True
    assert response["can_publish"] is False
    assert response["history"][0]["event_type"] == "reviews.response.drafted"
    assert (
        client.get(
            projection.replace(str(location), str(ids["sibling_location"])), headers=HEADERS
        ).status_code
        == 404
    )
    key = {"idempotency_key": "phase3-review-dispatch-key"}
    assert (
        client.post(f"{base}/{response_id}/publish", headers=HEADERS, json=key).status_code == 409
    )
    assert client.post(f"{base}/{response_id}/approve", headers=HEADERS).status_code == 200
    assert (
        client.post(f"{base}/{response_id}/publish", headers=HEADERS, json=key).status_code == 202
    )
    assert (
        client.post(f"{base}/{response_id}/publish", headers=HEADERS, json=key).status_code == 202
    )
    response = client.get(projection, headers=HEADERS).json()["responses"][0]
    assert response["status"] == "publishing"
    assert response["workflow_status"] == "queued"
    assert response["published_at"] is None
    assert response["external_response_id"] is None
    assert response["can_publish"] is False
    assert (
        sum(
            event["event_type"] == "reviews.response.publication_reserved"
            for event in response["history"]
        )
        == 1
    )


def test_approved_response_refuses_changed_review_at_dispatch(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]
    _ingest(postgresql_test_url, ids, body="First review", rating=4, external_id="phase3-drift")
    review, revision = _fetch_review_and_revision(postgresql_test_url, org, location)
    base = f"/api/v1/organizations/{org}/locations/{location}/reviews/{review}/responses"
    payload = {
        "review_revision_id": str(revision),
        "response_text": "Thanks for sharing.",
        "approved_fact_revision_ids": [_approved_fact(client, org)],
    }
    draft = client.post(base, headers=HEADERS, json=payload).json()["data"]["id"]
    assert client.post(f"{base}/{draft}/approve", headers=HEADERS).status_code == 200
    _ingest(postgresql_test_url, ids, body="Updated review", rating=2, external_id="phase3-drift")
    rejected = client.post(
        f"{base}/{draft}/publish",
        headers=HEADERS,
        json={"idempotency_key": "phase3-drift-dispatch"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "REVIEW_RESPONSE_NOT_PUBLISH_ELIGIBLE"


def test_provider_observed_response_needs_no_local_approval(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    from apps.api.app.products.reviews.service import ProviderReplyObservation

    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]

    async def observed(session: AsyncSession) -> UUID:
        async with session.begin():
            review, _, _ = await ReviewService().ingest(
                session,
                organization_id=org,
                location_id=location,
                integration_resource_id=ids["integration_resource"],
                external_review_id="provider-observed-phase3",
                provider="google_business_profile",
                rating=5,
                title=None,
                body="Synthetic visit",
                created_at=datetime.now(UTC),
                updated_at=None,
                correlation_id="phase3-provider-observed",
                provider_reply=ProviderReplyObservation(
                    comment="Existing provider reply",
                    updated_at=datetime.now(UTC),
                    state="APPROVED",
                    policy_violation=None,
                    external_response_id="synthetic-provider-review",
                ),
            )
            return review.id

    review = run_db(postgresql_test_url, observed)
    result = client.get(
        f"/api/v1/organizations/{org}/command-center/reviews/locations/{location}/{review}",
        headers=HEADERS,
    )
    assert result.status_code == 200
    response = result.json()["responses"][0]
    assert response["approval_required"] is False
    assert response["approved_at"] is None
    assert response["status"] == "published"
    assert result.json()["review"]["response_text"] == "Existing provider reply"
    assert response["published_at"] is not None
    assert response["workflow_status"] is None
    assert response["can_approve"] is False
    assert response["can_publish"] is False


def test_command_center_reviews_expose_reviewer_identity_and_status_filter(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    from apps.api.app.products.reviews.service import ReviewerObservation

    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]

    async def seed(session: AsyncSession) -> UUID:
        async with session.begin():
            first = None
            for key, reviewer in (
                (
                    "rid-named",
                    ReviewerObservation("named", "Jane Synthetic", "https://example.invalid/j.jpg"),
                ),
                ("rid-anon", ReviewerObservation("anonymous")),
                ("rid-unknown", None),
            ):
                review, _, _ = await ReviewService().ingest(
                    session,
                    organization_id=org,
                    location_id=location,
                    integration_resource_id=ids["integration_resource"],
                    external_review_id=key,
                    provider="google_business_profile",
                    rating=4,
                    title=None,
                    body="Synthetic visit",
                    created_at=datetime.now(UTC),
                    updated_at=None,
                    correlation_id=key,
                    reviewer=reviewer,
                )
                first = first or review.id
            assert first is not None
            return first

    review_id = run_db(postgresql_test_url, seed)
    path = f"/api/v1/organizations/{org}/command-center/reviews"
    body = client.get(path, headers=HEADERS, params={"location_id": str(location)}).json()
    by_id = {item["external_review_id"]: item for item in body["items"]}
    assert by_id["rid-named"]["reviewer_identity"] == "named"
    assert by_id["rid-named"]["reviewer_display_name"] == "Jane Synthetic"
    assert by_id["rid-named"]["reviewer_photo_url"] == "https://example.invalid/j.jpg"
    assert by_id["rid-anon"]["reviewer_identity"] == "anonymous"
    assert by_id["rid-anon"]["reviewer_display_name"] is None
    assert by_id["rid-unknown"]["reviewer_identity"] == "unknown"
    assert body["awaiting_response_count"] == 3
    published = client.get(
        path, headers=HEADERS, params={"location_id": str(location), "status": "published"}
    ).json()
    assert published["items"] == []
    needs = client.get(
        path, headers=HEADERS, params={"location_id": str(location), "status": "needs_response"}
    ).json()
    assert len(needs["items"]) == 3
    assert client.get(path, headers=HEADERS, params={"status": "bogus"}).status_code == 422
    detail = client.get(f"{path}/locations/{location}/{review_id}", headers=HEADERS).json()
    assert detail["review"]["reviewer_identity"] == "named"
