"""One opportunities list across SEO, content and growth, in constant queries."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from authorization.fixtures import add_effective_product_entitlement
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.agents.models import AgentRun, AgentSession
from apps.api.app.growth.models import GrowthAction, GrowthInitiative
from apps.api.app.products.content.models import ContentOpportunity
from apps.api.app.products.seo.models import SEOOpportunity, SEOPage, SEOWebsite

from .test_seo_api import HEADERS, seo_client

__all__ = ["seo_client"]


async def entitle_content(factory: async_sessionmaker[AsyncSession], organization: UUID) -> None:
    async with factory.begin() as session:
        await add_effective_product_entitlement(
            session, organization, "content", correlation_id="opps-content-entitlement"
        )


async def seed(
    factory: async_sessionmaker[AsyncSession], ids: dict[str, UUID], *, seo_count: int = 1
) -> dict[str, UUID]:
    organization, location = ids["organization"], ids["location"]
    async with factory.begin() as session:
        website = SEOWebsite(
            organization_id=organization,
            location_id=location,
            key="opps",
            name="Opps",
            canonical_origin="https://opps.example.test",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add(website)
        await session.flush()
        page = SEOPage(
            organization_id=organization,
            website_id=website.id,
            normalized_url="https://opps.example.test/menu",
            observed_url="https://opps.example.test/menu",
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
        for number in range(seo_count):
            session.add(
                SEOOpportunity(
                    organization_id=organization,
                    location_id=location,
                    website_id=website.id,
                    page_id=page.id,
                    opportunity_type="missing_meta_description",
                    deduplication_key=f"opps-{number}",
                    active_marker=f"opps-{number}",
                    evidence={"issue": "missing_meta_description", "source": "crawl"},
                    source_versions=["crawl.v1"],
                    score_version=1,
                    priority_score=80 - number,
                    score_explanation={},
                    status="identified",
                    attribution_state="attributed",
                )
            )
        content = ContentOpportunity(
            organization_id=organization,
            location_id=location,
            product_key="seo",
            target_reference="/blog/brunch",
            opportunity_type="seo",
            source_type="seo_analysis",
            source_reference="seed",
            evidence_document={"impressions": 1200, "clicks": 12},
            evidence_hash=uuid4().hex + uuid4().hex,
            priority_score=55,
            status="identified",
        )
        agent_session = AgentSession(
            organization_id=organization,
            location_id=location,
            skill_key="growth.planner",
            namespace_hash=uuid4().hex + uuid4().hex,
            hermes_session_key=uuid4().hex,
            status="active",
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            version=1,
        )
        session.add_all([content, agent_session])
        await session.flush()
        run = AgentRun(
            organization_id=organization,
            location_id=location,
            workflow_run_id=ids["workflow_run"],
            agent_session_id=agent_session.id,
            skill_key="growth.planner",
            skill_version=6,
            hermes_session_id=agent_session.hermes_session_key,
            correlation_id="opps-test",
            status="completed",
            capability_snapshot={},
            output_references=[],
            source_references=[],
            event_count=0,
        )
        session.add(run)
        await session.flush()
        growth = GrowthInitiative(
            organization_id=organization,
            location_id=location,
            planner_agent_run_id=run.id,
            idempotency_key=f"growth-{uuid4().hex[:8]}",
            objective="Win brunch searches",
            rationale="Demand exists",
            source_references=[{"a": 1}, {"b": 2}],
            priority_score=65,
            confidence=Decimal("0.8"),
            status="proposed",
        )
        session.add(growth)
        await session.flush()
        session.add(
            GrowthAction(
                organization_id=organization,
                initiative_id=growth.id,
                action_key="a1",
                product_key="seo",
                action_type="site_implementation",
                target_reference="/menu",
                execution_mode="manual",
                dependency_keys=[],
                evidence_references=[],
                expected_result_hypothesis="More clicks",
                verification_plan={},
                risk="low",
                effort="low",
                position=0,
                status="proposed",
            )
        )
        await session.flush()
        return {"content": content.id, "growth": growth.id, "page": page.id, "website": website.id}


def test_one_list_carries_every_kind_with_typed_fields_and_never_hides_unconfigured_clients(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    seeded = asyncio.run(seed(seo_session_factory, ids))
    base = f"/api/v1/organizations/{ids['organization']}/command-center/opportunities"
    unentitled = client.get(base, headers=HEADERS).json()
    # A kind the client is not entitled to is labeled unavailable, not shown as an empty list.
    assert unentitled["kinds_unavailable"] == ["content"]
    assert {row["kind"] for row in unentitled["data"]} == {"seo", "growth"}
    asyncio.run(entitle_content(seo_session_factory, ids["organization"]))
    response = client.get(base, headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    by_kind = {row["kind"]: row for row in body["data"]}
    assert set(by_kind) == {"seo", "content", "growth"}
    assert [row["priority"] for row in body["data"]] == sorted(
        (row["priority"] for row in body["data"]), reverse=True
    )
    seo = by_kind["seo"]
    assert seo["id"] == f"seo_opportunity:{seo['source_id']}"
    assert seo["client"]["slug"] == "seo-test-org"
    assert seo["priority_band"] == "high"
    assert seo["next_action"] == "request_recommendation"
    # No publishing target exists: disabled with a typed reason, and never hidden.
    assert seo["site_change"] == "not_configured"
    assert seo["site_change_reason"] == "SITE_CHANGES_NOT_CONFIGURED"
    assert seo["evidence_summary"]["signal"] == "missing_meta_description"
    content = by_kind["content"]
    assert content["source_id"] == str(seeded["content"])
    assert content["site_change"] == "not_applicable"
    assert content["next_action"] == "review_opportunity"
    assert {m["key"]: m["value"] for m in content["evidence_summary"]["metrics"]} == {
        "clicks": 12.0,
        "impressions": 1200.0,
    }
    growth = by_kind["growth"]
    assert growth["headline"] == "Win brunch searches"
    assert growth["confidence"] == 0.8
    assert growth["next_action"] == "review_growth_plan"
    assert growth["evidence_summary"]["source_count"] == 2
    only = client.get(base + "?kind=growth", headers=HEADERS).json()["data"]
    assert [row["kind"] for row in only] == ["growth"]
    medium = client.get(base + "?priority=medium", headers=HEADERS).json()["data"]
    assert {row["kind"] for row in medium} == {"content", "growth"}
    assert client.get(base + "?kind=other", headers=HEADERS).status_code == 422


def test_detail_resolves_each_kind_and_denies_foreign_scope(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    seeded = asyncio.run(seed(seo_session_factory, ids))
    asyncio.run(entitle_content(seo_session_factory, ids["organization"]))
    base = f"/api/v1/organizations/{ids['organization']}/command-center/opportunities"
    growth = client.get(f"{base}/{seeded['growth']}", headers=HEADERS)
    assert growth.status_code == 200, growth.text
    body = growth.json()
    assert body["kind"] == "growth"
    assert body["growth"]["objective"] == "Win brunch searches"
    assert [a["action_key"] for a in body["growth"]["actions"]] == ["a1"]
    assert isinstance(body["can_approve"], bool)
    content = client.get(f"{base}/{seeded['content']}", headers=HEADERS)
    assert content.status_code == 200, content.text
    assert content.json()["kind"] == "content"
    assert content.json()["content"]["target_reference"] == "/blog/brunch"
    row = client.get(base + "?kind=seo", headers=HEADERS).json()["data"][0]
    seo = client.get(f"{base}/{row['source_id']}", headers=HEADERS)
    assert seo.status_code == 200, seo.text
    assert seo.json()["kind"] == "seo"
    assert seo.json()["live_check"] is None
    foreign = f"/api/v1/organizations/{ids['other_organization']}/command-center/opportunities"
    for source in (seeded["growth"], seeded["content"], row["source_id"]):
        denied = client.get(f"{foreign}/{source}", headers=HEADERS)
        assert denied.status_code in {403, 404}
        assert str(source) not in denied.text
    assert client.get(foreign, headers=HEADERS).status_code in {403, 404}
    assert client.get(f"{base}/{uuid4()}", headers=HEADERS).status_code == 404


def test_statement_count_does_not_grow_with_opportunities(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    seeded = asyncio.run(seed(seo_session_factory, ids, seo_count=1))
    base = f"/api/v1/organizations/{ids['organization']}/command-center/opportunities"
    statements: list[str] = []

    def record(_c: object, _cur: object, statement: str, *_: object) -> None:
        statements.append(statement)

    async def more() -> None:
        async with seo_session_factory.begin() as session:
            for number in range(10, 20):
                session.add(
                    SEOOpportunity(
                        organization_id=ids["organization"],
                        location_id=ids["location"],
                        website_id=seeded["website"],
                        page_id=seeded["page"],
                        opportunity_type="missing_title",
                        deduplication_key=f"opps-{number}",
                        active_marker=f"opps-{number}",
                        evidence={"issue": "missing_title"},
                        source_versions=["crawl.v1"],
                        score_version=1,
                        priority_score=30 + number,
                        score_explanation={},
                        status="identified",
                        attribution_state="attributed",
                    )
                )

    engine = seo_session_factory.kw["bind"].sync_engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        assert client.get(base, headers=HEADERS).status_code == 200
        first = len(statements)
        statements.clear()
        asyncio.run(more())
        statements.clear()
        listed = client.get(base, headers=HEADERS)
        assert listed.status_code == 200
        # 11 SEO + 1 growth; content is not entitled in this fixture.
        assert len(listed.json()["data"]) == 12
    finally:
        event.remove(engine, "before_cursor_execute", record)
    # Ten more opportunities add no statements: every read is set-based.
    assert len(statements) == first, (first, len(statements))


def test_portfolio_list_is_tenant_scoped_and_filters_by_client(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    asyncio.run(seed(seo_session_factory, ids))
    asyncio.run(entitle_content(seo_session_factory, ids["organization"]))
    listed = client.get("/api/v1/command-center/opportunities", headers=HEADERS)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert {row["kind"] for row in body["data"]} == {"seo", "content", "growth"}
    assert {row["client"]["slug"] for row in body["data"]} == {"seo-test-org"}
    assert str(ids["other_organization"]) not in listed.text
    own = client.get(
        f"/api/v1/command-center/opportunities?organization_id={ids['organization']}",
        headers=HEADERS,
    )
    assert own.status_code == 200
    assert len(own.json()["data"]) == len(body["data"])
    foreign = client.get(
        f"/api/v1/command-center/opportunities?organization_id={ids['other_organization']}",
        headers=HEADERS,
    )
    assert foreign.status_code == 404
    assert client.get("/api/v1/command-center/opportunities").status_code == 401
