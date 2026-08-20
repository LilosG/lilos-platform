"""Business Knowledge ingestion, retrieval, and lifecycle tests.

Covers:
 - GBP snapshot → knowledge document
 - SEO page → knowledge document
 - Hash change → new version (supersedes)
 - Retrieval scoping for content context
 - Tenant isolation
 - Provenance on AIExecution
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.administration.knowledge_service import BusinessKnowledgeService
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import ContentBrief, ContentItem
from apps.api.app.products.content.service import ContentService

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_organization(
    session: AsyncSession, org_id: UUID, name: str = "Test Org"
) -> Organization:
    org = Organization(
        id=org_id,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{org_id.hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()
    return org


async def _seed_user(session: AsyncSession, user_id: UUID) -> UserProfile:
    user = UserProfile(id=user_id, auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
    session.add(user)
    await session.flush()
    return user


async def _seed_location(
    session: AsyncSession, org_id: UUID, loc_id: UUID, name: str = "Test Location"
) -> Location:
    loc = Location(
        id=loc_id,
        organization_id=org_id,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{loc_id.hex[:8]}",
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url="https://example.invalid",
        is_primary=True,
        version=1,
    )
    session.add(loc)
    await session.flush()
    return loc


# ── GBP snapshot → knowledge ─────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_snapshot_ingestion_creates_knowledge_document(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ingesting a GBP profile snapshot creates a structured knowledge document."""
    async with content_session_factory() as session:
        org_id = uuid4()
        loc_id = uuid4()
        await _seed_organization(session, org_id)
        await _seed_location(session, org_id, loc_id)

        snapshot_id = uuid4()
        gbp_loc_id = uuid4()
        profile: dict[str, object] = {
            "categories": [
                {"displayName": "Plumber"},
                {"displayName": "HVAC Contractor"},
            ],
            "serviceItems": [
                {"structuredName": "water_heater_installation"},
            ],
            "regularHours": {"periods": [{"openDay": "MONDAY", "closeDay": "MONDAY"}]},
        }

        svc = BusinessKnowledgeService()
        docs = await svc.ingest_gbp_snapshot(
            session,
            organization_id=org_id,
            gbp_location_id=gbp_loc_id,
            location_id=loc_id,
            snapshot_id=snapshot_id,
            normalized_profile=profile,
            content_hash="abc123",
        )

        assert len(docs) >= 1
        doc = docs[0]
        assert doc.source_type == "gbp_profile_snapshot"
        assert doc.source_reference == str(snapshot_id)
        assert doc.authority == "provider_observed"
        assert doc.content_type == "structured_facts"
        assert doc.status == "active"
        assert doc.organization_id == org_id
        assert doc.location_id == loc_id
        categories: list[object] = doc.content.get("categories", [])  # type: ignore[assignment]
        assert any("Plumber" in str(c) for c in categories)
        service_items: list[object] = doc.content.get("service_items", [])  # type: ignore[assignment]
        assert any("water_heater_installation" in str(s) for s in service_items)


@pytest.mark.integration
@pytest.mark.anyio
async def test_gbp_snapshot_idempotent_same_hash(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ingesting the same snapshot twice with the same hash is idempotent."""
    async with content_session_factory() as session:
        org_id = uuid4()
        loc_id = uuid4()
        await _seed_organization(session, org_id)
        await _seed_location(session, org_id, loc_id)

        svc = BusinessKnowledgeService()
        profile: dict[str, object] = {"categories": [{"displayName": "Plumber"}]}
        gbp_loc_id = uuid4()
        snapshot_id = uuid4()

        docs1 = await svc.ingest_gbp_snapshot(
            session,
            organization_id=org_id,
            gbp_location_id=gbp_loc_id,
            location_id=loc_id,
            snapshot_id=snapshot_id,
            normalized_profile=profile,
            content_hash="same-hash",
        )
        docs2 = await svc.ingest_gbp_snapshot(
            session,
            organization_id=org_id,
            gbp_location_id=gbp_loc_id,
            location_id=loc_id,
            snapshot_id=snapshot_id,
            normalized_profile=profile,
            content_hash="same-hash",
        )

        assert len(docs1) >= 1
        assert len(docs2) == 0  # no new document created


# ── SEO page → knowledge ─────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.anyio
async def test_seo_page_ingestion_creates_knowledge_document(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ingesting a crawled SEO page creates a page_text knowledge document."""
    async with content_session_factory() as session:
        org_id = uuid4()
        loc_id = uuid4()
        await _seed_organization(session, org_id)
        await _seed_location(session, org_id, loc_id)

        svc = BusinessKnowledgeService()
        doc = await svc.ingest_seo_page(
            session,
            organization_id=org_id,
            location_id=loc_id,
            page_id=uuid4(),
            normalized_url="https://example.com/services/plumbing",
            title="Plumbing Services | Example Co",
            h1="Professional Plumbing Services",
            meta_description="Expert plumbing in Seattle",
            body_text="We offer water heater installation, drain cleaning, and emergency repairs.",
            content_hash="seo-hash-1",
        )

        assert doc is not None
        assert doc.source_type == "seo_page"
        assert doc.authority == "system_derived"
        assert doc.content_type == "page_text"
        assert doc.organization_id == org_id
        assert doc.location_id == loc_id
        assert "water heater" in str(doc.content)


# ── Hash change → new version ────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.anyio
async def test_hash_change_supersedes_old_version(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """When content hash changes, the old document is superseded."""
    async with content_session_factory() as session:
        org_id = uuid4()
        loc_id = uuid4()
        await _seed_organization(session, org_id)
        await _seed_location(session, org_id, loc_id)

        svc = BusinessKnowledgeService()
        page_id = uuid4()

        doc1 = await svc.ingest_seo_page(
            session,
            organization_id=org_id,
            location_id=loc_id,
            page_id=page_id,
            normalized_url="https://ex.com/page",
            title="Old Title",
            h1="Old H1",
            meta_description=None,
            body_text="Old body.",
            content_hash="hash-v1",
        )
        assert doc1 is not None
        assert doc1.status == "active"

        doc2 = await svc.ingest_seo_page(
            session,
            organization_id=org_id,
            location_id=loc_id,
            page_id=page_id,
            normalized_url="https://ex.com/page",
            title="New Title",
            h1="New H1",
            meta_description=None,
            body_text="New body.",
            content_hash="hash-v2",
        )
        assert doc2 is not None
        assert doc2.status == "active"
        assert doc2.supersedes_id == doc1.id

        # Reload doc1 — should be superseded
        await session.refresh(doc1)
        assert doc1.status == "superseded"


# ── Retrieval scoping ────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.anyio
async def test_retrieval_scopes_to_relevant_pages(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An EV-charger content brief retrieves EV/electrical pages, not plumbing."""
    async with content_session_factory() as session:
        org_id = uuid4()
        loc_id = uuid4()
        await _seed_organization(session, org_id)
        await _seed_location(session, org_id, loc_id)

        svc = BusinessKnowledgeService()

        # Ingest relevant page
        await svc.ingest_seo_page(
            session,
            organization_id=org_id,
            location_id=loc_id,
            page_id=uuid4(),
            normalized_url="https://ex.com/ev-charging",
            title="EV Charger Installation",
            h1="Commercial EV Charging",
            meta_description="EV charger installs",
            body_text="We install Level 2 chargers.",
            content_hash="ev-hash",
        )
        # Ingest irrelevant page
        await svc.ingest_seo_page(
            session,
            organization_id=org_id,
            location_id=loc_id,
            page_id=uuid4(),
            normalized_url="https://ex.com/plumbing",
            title="Plumbing Services",
            h1="Plumbing Repairs",
            meta_description="Plumbing services",
            body_text="We fix leaky faucets.",
            content_hash="plumbing-hash",
        )

        result = await svc.retrieve_for_content(
            session,
            organization_id=org_id,
            location_id=loc_id,
            content_title="Commercial EV Charger Installation Guide",
            audience="business owners",
            intent="educate about EV charging options",
            content_type="blog",
            limit=10,
        )

        website_knowledge = result["website_knowledge"]
        urls = [str(k.get("url", "")) for k in website_knowledge]
        ev_urls = [u for u in urls if "ev" in u]
        plumbing_urls = [u for u in urls if "plumbing" in u]

        # EV page should be included, plumbing excluded
        assert len(ev_urls) > 0, f"EV page not found in results: {urls}"
        assert len(plumbing_urls) == 0, f"Plumbing page should be excluded: {urls}"


# ── Tenant isolation ─────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.anyio
async def test_knowledge_tenant_isolation(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Knowledge from one organization is not visible to another."""
    async with content_session_factory() as session:
        org_a = uuid4()
        org_b = uuid4()
        await _seed_organization(session, org_a, "Org A")
        await _seed_organization(session, org_b, "Org B")

        svc = BusinessKnowledgeService()

        # Ingest into org A
        await svc.ingest_seo_page(
            session,
            organization_id=org_a,
            location_id=None,
            page_id=uuid4(),
            normalized_url="https://a.com/page",
            title="A Page",
            h1="A",
            meta_description=None,
            body_text="Secret A content.",
            content_hash="a-hash",
        )

        # Retrieve for org B — should see nothing
        result = await svc.retrieve_for_content(
            session,
            organization_id=org_b,
            location_id=None,
            content_title="Anything",
            audience="any",
            intent="any",
            content_type="blog",
        )
        assert result["source_document_ids"] == []
        assert result["website_knowledge"] == []


# ── AIExecution provenance ───────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.anyio
async def test_ai_execution_includes_knowledge_source_refs(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An AI draft execution's input_references include knowledge document IDs."""
    from apps.api.app.administration.models import BusinessFactRevision

    async with content_session_factory() as session:
        org_id = uuid4()
        user_id = uuid4()
        await _seed_organization(session, org_id)
        await _seed_user(session, user_id)
        await _seed_location(session, org_id, uuid4())

        # Ingest some knowledge
        svc = BusinessKnowledgeService()
        await svc.ingest_seo_page(
            session,
            organization_id=org_id,
            location_id=None,
            page_id=uuid4(),
            normalized_url="https://ex.com/services",
            title="Our Services",
            h1="Quality Services",
            meta_description=None,
            body_text="We offer quality services including installation and repair.",
            content_hash="svc-hash",
        )

        # Create item + brief + fact
        item_id = uuid4()
        brief_id = uuid4()
        fact_id = uuid4()

        fact = BusinessFactRevision(
            id=fact_id,
            organization_id=org_id,
            fact_identity=uuid4(),
            fact_key="business.name",
            value_type="string",
            value="TestCo",
            source="client_input",
            authority="client_approved",
            status="approved",
            revision=1,
            proposed_by=user_id,
            approved_by=user_id,
            approved_at=datetime.now(UTC),
            change_reason="test",
        )
        item = ContentItem(
            id=item_id,
            organization_id=org_id,
            content_type="blog",
            title="Quality Services Guide",
            slug="quality-services",
            status="brief_ready",
        )
        brief = ContentBrief(
            id=brief_id,
            organization_id=org_id,
            content_item_id=item_id,
            revision_number=1,
            audience="homeowners",
            intent="explain our quality services",
            target_reference="/quality-services",
            approved_fact_revision_ids=[str(fact_id)],
            required_claims=[],
            prohibited_claims=[],
            required_local_references=[],
            source_evidence_references=[],
            validation_requirements={},
            status="ready",
        )
        session.add(item)
        await session.flush()
        session.add_all([brief, fact])
        await session.flush()

        content_svc = ContentService()
        idemp_key = f"provenance-{uuid4().hex[:16]}"
        _revision, execution = await content_svc.execute_ai_draft_workflow(
            session,
            organization_id=org_id,
            item_id=item_id,
            brief_id=brief_id,
            idempotency_key=idemp_key,
            user_id=None,
            correlation_id="test-provenance",
        )

        # input_references should contain knowledge doc IDs beyond just brief.id
        refs = execution.input_references
        assert len(refs) > 1, f"Expected knowledge refs, got: {refs}"
        brief_ref = str(brief_id)
        assert brief_ref in refs

        # At least one ref should be a UUID that isn't the brief
        non_brief_refs = [r for r in refs if r != brief_ref]
        assert len(non_brief_refs) > 0, f"No knowledge doc refs found: {refs}"


# ── Conflict detection ───────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.anyio
async def test_conflicting_business_names_create_pending_confirmation(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """When GBP and organization profile have different business names,
    a pending_approval fact is created — no silent overwrite."""
    from apps.api.app.administration.models import BusinessFactRevision

    async with content_session_factory() as session:
        org_id = uuid4()
        user_id = uuid4()
        await _seed_organization(session, org_id, "GBP Name Co")
        await _seed_user(session, user_id)

        svc = BusinessKnowledgeService()

        # Ingest GBP knowledge with a different name
        gbp_profile: dict[str, object] = {
            "locationName": "GBP Name Co",
            "categories": [{"displayName": "Plumber"}],
        }
        await svc.ingest_gbp_snapshot(
            session,
            organization_id=org_id,
            gbp_location_id=uuid4(),
            location_id=None,
            snapshot_id=uuid4(),
            normalized_profile=gbp_profile,
            content_hash="gbp-hash-1",
        )
        # Ingest org identity with a different name
        await svc.ingest_organization_identity(
            session,
            organization_id=org_id,
            org_name="Profile Name Inc",
        )

        # Detect conflicts
        conflicts = await svc.detect_conflicts(session, organization_id=org_id, actor_id=user_id)

        # Should have created a pending_approval fact for business.name
        assert len(conflicts) > 0
        conflict = conflicts[0]
        assert conflict["fact_key"] == "business.name"

        # Verify the fact was persisted
        fact_id_str = str(conflict["fact_id"])
        fact = await session.scalar(
            select(BusinessFactRevision).where(BusinessFactRevision.id == UUID(fact_id_str))
        )
        assert fact is not None
        assert fact.status == "pending_approval"
        assert fact.authority == "system_derived"


@pytest.mark.integration
@pytest.mark.anyio
async def test_no_conflict_when_names_agree(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """When all sources agree on the business name, no conflict is created."""
    async with content_session_factory() as session:
        org_id = uuid4()
        user_id = uuid4()
        await _seed_organization(session, org_id, "Same Name Co")
        await _seed_user(session, user_id)

        svc = BusinessKnowledgeService()
        await svc.ingest_organization_identity(
            session, organization_id=org_id, org_name="Same Name Co"
        )

        conflicts = await svc.detect_conflicts(session, organization_id=org_id, actor_id=user_id)
        assert len(conflicts) == 0


# ── Backfill ─────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.anyio
async def test_backfill_from_existing_data_is_idempotent(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Backfill creates knowledge from existing data and is idempotent."""
    async with content_session_factory() as session:
        org_id = uuid4()
        await _seed_organization(session, org_id, "Backfill Org")

        svc = BusinessKnowledgeService()

        # First backfill
        counts1 = await svc.backfill_from_existing_data(session, organization_id=org_id)
        # Second backfill — should be idempotent
        counts2 = await svc.backfill_from_existing_data(session, organization_id=org_id)

        # Identity should be created once
        assert counts1["identity"] <= 1
        # Second run should create no new documents
        assert counts2["identity"] == 0
        assert counts2["gbp"] == 0
        assert counts2["seo"] == 0
