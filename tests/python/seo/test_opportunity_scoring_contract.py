"""SEO orchestration relies on the shared deterministic scoring contract."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.seo.service import (
    inferred_business_value,
    opportunity_score,
    page_business_importance,
)


def test_opportunity_score_stays_in_platform_bounds() -> None:
    score, explanation = opportunity_score(
        search_potential=100,
        business_value=100,
        relevance=100,
        confidence=100,
        urgency=100,
        effort=0,
    )
    assert 0 <= score <= 100
    assert explanation["final_score"] == score


@pytest.mark.parametrize(
    ("key_events", "expected"),
    [(1, 40), (2, 40), (3, 55), (5, 55), (6, 70), (10, 70), (11, 85), (24, 85), (25, 100)],
)
def test_business_importance_tiers(key_events: int, expected: int) -> None:
    assert inferred_business_value(key_events) == expected


def test_unavailable_business_component_is_omitted_and_normalized() -> None:
    score, explanation = opportunity_score(
        search_potential=45,
        business_value=None,
        relevance=85,
        confidence=95,
        urgency=55,
        effort=25,
    )
    assert score == round((45 * 2 + 85 * 2 + 95 * 2 + 55 - 25) / 6)
    assert explanation["business_value"] is None
    assert explanation["business_component"] == "omitted"
    assert explanation["business_importance_state"] == "unavailable"
    assert explanation["score_policy_version"] == "opportunity_score.v2"


@pytest.mark.anyio
async def test_page_business_importance_requires_exact_fresh_scoped_evidence() -> None:
    now = datetime.now(UTC)
    organization_id, website_id, page_id = uuid4(), uuid4(), uuid4()
    prop = SimpleNamespace(
        id=uuid4(),
        external_property_id="properties/123",
        provider="google_analytics",
        page_evidence_status="observed",
        freshness_status="fresh",
        last_synced_at=now,
    )
    observation = SimpleNamespace(
        id=uuid4(),
        page_id=page_id,
        quality_state="valid",
        completeness=Decimal("1.0"),
        value=Decimal(6),
        dimensions={
            "observation_type": "organic_landing_page",
            "website_id": str(website_id),
            "hostName": "example.invalid",
            "sessionDefaultChannelGroup": "Organic Search",
        },
        provenance={
            "ingested_at": now.isoformat(),
            "mapping_state": "mapped",
            "mapping_basis": "exact_normalized_url",
            "resolver_version": "page_identity.v1",
            "provider": "google_analytics",
            "property": "properties/123",
            "report": "organic_landing_page",
            "availability": "observed",
            "window_days": 28,
            "website_id": str(website_id),
            "raw_host_name": "example.invalid",
        },
    )
    definition = SimpleNamespace(key="ga4.organicLanding.keyEvents", version=1)
    source = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(
        scalars=AsyncMock(return_value=[prop]),
        execute=AsyncMock(return_value=[(observation, definition, source)]),
    )

    async def resolve() -> dict[UUID, dict[str, object]]:
        return await page_business_importance(
            cast(AsyncSession, session),
            organization_id,
            website_id,
            "https://example.invalid/",
            None,
            {page_id},
            now=now,
        )

    assert (await resolve())[page_id]["business_value"] == 70
    observation.provenance["mapping_state"] = "ambiguous"
    assert (await resolve())[page_id]["business_importance_state"] == "unavailable"
    observation.provenance["mapping_state"] = "mapped"
    observation.dimensions["hostName"] = "foreign.invalid"
    assert (await resolve())[page_id]["business_importance_state"] == "unavailable"
    observation.dimensions["hostName"] = "example.invalid"
    observation.value = Decimal(0)
    observation.quality_state = "zero"
    zero = (await resolve())[page_id]
    assert zero["business_value"] is None
    assert "Zero key events" in str(zero["limitation"])
