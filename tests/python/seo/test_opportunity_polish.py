"""Opportunities list: one item per finding, open vs done, live state, site-change availability."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.products.content.models import (
    ContentOpportunity,
    ContentPublication,
    PublishingTarget,
)
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOPage,
    SEORecommendationRevision,
    SEOWebsite,
)
from apps.api.app.routes.opportunity_subjects import growth_headline

from .test_command_center_opportunities import entitle_content
from .test_seo_api import HEADERS, seo_client

__all__ = ["seo_client"]

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
MAPPED_FIELD = {
    "file_path": "src/content/menu.json",
    "source_type": "keystatic_json",
    "json_pointer": ["singleton", "seo", "title"],
}


def opportunity(
    ids: dict[str, UUID], website: UUID, page: UUID | None, **values: object
) -> SEOOpportunity:
    key = uuid4().hex[:12]
    base: dict[str, object] = {
        "organization_id": ids["organization"],
        "location_id": ids["location"],
        "website_id": website,
        "page_id": page,
        "opportunity_type": "gsc_low_ctr",
        "deduplication_key": key,
        "active_marker": key[:8],
        "evidence": {"query": "brunch spots san diego", "source": "gsc"},
        "source_versions": ["gsc.v1"],
        "score_version": 1,
        "priority_score": 90,
        "score_explanation": {},
        "status": "approved",
        "attribution_state": "attributed" if page else "query_only",
    }
    return SEOOpportunity(**{**base, **values})


async def seed_website(
    factory: async_sessionmaker[AsyncSession], ids: dict[str, UUID]
) -> tuple[UUID, UUID]:
    async with factory.begin() as session:
        website = SEOWebsite(
            organization_id=ids["organization"],
            location_id=ids["location"],
            key="polish",
            name="Polish",
            canonical_origin="https://polish.example.test",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add(website)
        await session.flush()
        page = SEOPage(
            organization_id=ids["organization"],
            website_id=website.id,
            normalized_url="https://polish.example.test/menu",
            observed_url="https://polish.example.test/menu",
            normalization_reasons=[],
            robots_directives=[],
            internal_links=[],
            external_links=[],
            structured_data_present=False,
            indexability="indexable",
            technical_issues=[],
            quality_status="clean",
        )
        session.add(page)
        await session.flush()
        return website.id, page.id


async def add_target(factory: async_sessionmaker[AsyncSession], ids: dict[str, UUID]) -> UUID:
    """The shape Coco Maya has: one active target whose page map covers some pages."""
    async with factory.begin() as session:
        provider = Provider(
            key=f"github-{uuid4().hex[:8]}",
            name="GitHub",
            status="active",
            capabilities=["content.publish"],
            manifest_version=1,
        )
        session.add(provider)
        await session.flush()
        connection = IntegrationConnection(
            organization_id=ids["organization"],
            provider_id=provider.id,
            external_account_reference="org/site",
            status="connected",
            version=1,
        )
        session.add(connection)
        await session.flush()
        target = PublishingTarget(
            organization_id=ids["organization"],
            connection_id=connection.id,
            key="primary",
            target_type="github_astro",
            repository_id="org/site",
            base_branch="main",
            allowed_path_prefix="src/content/blog",
            allowed_site_change_prefixes=["src/content"],
            frontmatter_contract={"page_map": {"/menu": {"seo_title": MAPPED_FIELD}}},
            status="active",
            version=1,
        )
        session.add(target)
        await session.flush()
        return target.id


def url(ids: dict[str, UUID], query: str = "") -> str:
    return f"/api/v1/organizations/{ids['organization']}/command-center/opportunities{query}"


def test_site_changes_follow_the_organizations_page_map_not_the_row(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    website, page = asyncio.run(seed_website(seo_session_factory, ids))

    async def rows() -> None:
        async with seo_session_factory.begin() as session:
            session.add_all(
                [
                    opportunity(ids, website, None, evidence={"query": "no page yet"}),
                    opportunity(
                        ids,
                        website,
                        page,
                        evidence={"query": "mapped page"},
                        opportunity_type="gsc_striking_distance",
                    ),
                ]
            )

    asyncio.run(rows())
    before = {
        r["subject"]["query"]: r for r in client.get(url(ids), headers=HEADERS).json()["data"]
    }
    assert before["no page yet"]["site_change"] == "not_configured"
    asyncio.run(add_target(seo_session_factory, ids))
    after = {r["subject"]["query"]: r for r in client.get(url(ids), headers=HEADERS).json()["data"]}
    # An opportunity with no page of its own is available once the client's target maps pages.
    assert after["no page yet"]["site_change"] == "configured"
    assert after["no page yet"]["site_change_reason"] is None
    assert after["mapped page"]["site_change"] == "configured"
    assert after["mapped page"]["subject"]["path"] == "/menu"


def test_one_item_per_finding_newest_wins_and_older_sightings_become_history(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    website, page = asyncio.run(seed_website(seo_session_factory, ids))

    async def rows() -> dict[str, UUID]:
        async with seo_session_factory.begin() as session:
            older = opportunity(ids, website, None, status="approved", priority_score=90)
            older.updated_at = NOW - timedelta(days=5)
            newer = opportunity(ids, website, page, status="approved", priority_score=92)
            newer.updated_at = NOW
            gone = opportunity(ids, website, None, status="archived", priority_score=70)
            gone.updated_at = NOW - timedelta(days=9)
            other = opportunity(
                ids, website, None, evidence={"query": "date night"}, status="recommended"
            )
            session.add_all([older, newer, gone, other])
            await session.flush()
            return {"older": older.id, "newer": newer.id, "gone": gone.id}

    seeded = asyncio.run(rows())
    listed = client.get(url(ids), headers=HEADERS).json()["data"]
    brunch = [r for r in listed if r["subject"]["query"] == "brunch spots san diego"]
    assert [r["source_id"] for r in brunch] == [str(seeded["newer"])]
    assert {o["id"] for o in brunch[0]["earlier_observations"]} == {
        str(seeded["older"]),
        str(seeded["gone"]),
    }
    assert len(listed) == 2
    # Nothing is deleted: the older observations are still there for the Done view and detail.
    detail = client.get(url(ids, f"/{seeded['newer']}"), headers=HEADERS).json()
    assert len(detail["data"]["earlier_observations"]) == 2
    done = client.get(url(ids, "?state=done"), headers=HEADERS).json()["data"]
    assert [r["source_id"] for r in done] == [str(seeded["gone"])]


def test_live_verified_change_is_done_work_with_measure_impact_next(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    website, page = asyncio.run(seed_website(seo_session_factory, ids))
    target = asyncio.run(add_target(seo_session_factory, ids))

    async def rows() -> UUID:
        async with seo_session_factory.begin() as session:
            live = opportunity(ids, website, page, evidence={"query": "live one"})
            pending = opportunity(ids, website, page, evidence={"query": "pending one"})
            session.add_all([live, pending])
            await session.flush()
            revisions = []
            for item in (live, pending):
                revision = SEORecommendationRevision(
                    organization_id=ids["organization"],
                    opportunity_id=item.id,
                    revision_number=1,
                    proposed_action="Rewrite the title",
                    evidence_references=[],
                    expected_result_hypothesis="More clicks",
                    risk="low",
                    effort="low",
                    status="approved",
                    created_at=NOW,
                )
                session.add(revision)
                revisions.append(revision)
            await session.flush()
            for revision, state in zip(revisions, ("verified", "pending"), strict=True):
                session.add(
                    ContentPublication(
                        organization_id=ids["organization"],
                        publication_kind="site_change",
                        seo_recommendation_revision_id=revision.id,
                        publishing_target_id=target,
                        workflow_run_id=ids["workflow_run"],
                        idempotency_key=f"live-{revision.id}",
                        status="verified" if state == "verified" else "deployment_pending",
                        target_path="src/content/menu.json",
                        verification_status=state,
                        verified_at=NOW if state == "verified" else None,
                    )
                )
            return live.id

    live_id = asyncio.run(rows())
    open_rows = client.get(url(ids), headers=HEADERS).json()["data"]
    assert [r["subject"]["query"] for r in open_rows] == ["pending one"]
    assert open_rows[0]["next_action"] == "monitor_publication"
    assert open_rows[0]["lifecycle"] == "open"
    done = client.get(url(ids, "?state=done"), headers=HEADERS).json()["data"]
    assert [r["source_id"] for r in done] == [str(live_id)]
    assert done[0]["lifecycle"] == "live"
    assert done[0]["next_action"] == "measure_impact"
    assert done[0]["verified_at"].startswith("2026-10-05")
    detail = client.get(url(ids, f"/{live_id}"), headers=HEADERS).json()
    assert detail["data"]["lifecycle"] == "live"
    assert detail["data"]["next_action"] == "measure_impact"


def test_content_subjects_come_from_the_linked_query_or_page_and_growth_gets_a_short_title(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    website, page = asyncio.run(seed_website(seo_session_factory, ids))
    asyncio.run(entitle_content(seo_session_factory, ids["organization"]))

    async def rows() -> None:
        async with seo_session_factory.begin() as session:
            source = opportunity(ids, website, None, evidence={"query": "brunch spots san diego"})
            session.add(source)
            await session.flush()
            for reference in (
                f"seo-opportunity:{source.id}",
                f"seo-opportunity:{uuid4()}",
                "https://polish.example.test/blog/best-brunch",
            ):
                session.add(
                    ContentOpportunity(
                        organization_id=ids["organization"],
                        location_id=ids["location"],
                        product_key="seo",
                        target_reference=reference,
                        opportunity_type="seo",
                        source_type="seo_analysis",
                        source_reference="seed",
                        evidence_document={},
                        evidence_hash=uuid4().hex + uuid4().hex,
                        priority_score=55,
                        status="identified",
                    )
                )

    asyncio.run(rows())
    content = [r for r in client.get(url(ids, "?kind=content"), headers=HEADERS).json()["data"]]
    subjects = sorted((r["subject"]["query"] or "", r["subject"]["path"] or "") for r in content)
    assert subjects == [("", ""), ("", "/blog/best-brunch"), ("brunch spots san diego", "")]
    assert all(r["headline"] is None for r in content)


def test_growth_headline_is_short_and_cut_at_a_word() -> None:
    assert growth_headline("Win brunch searches") == "Win brunch searches"
    assert (
        growth_headline("Diagnostic: test agent.content as executor workflow key.") == "Diagnostic"
    )
    long = (
        "Recover click-through from Coco Maya's growing organic visibility by closing the "
        "technical and mobile-performance gaps that depress rankings across the site"
    )
    headline = growth_headline(long)
    assert len(headline) <= 90
    assert headline.endswith("…")
    assert long.startswith(headline.removesuffix("…"))
    assert not headline.removesuffix("…").endswith(" ")
    assert long[len(headline) - 1] == " "
