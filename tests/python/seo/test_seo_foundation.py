import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.app.products.seo.service import (
    metric_value,
    normalize_url,
    opportunity_score,
    validate_crawl_target,
)


def test_url_normalization_preserves_www_path_query_and_removes_fragment() -> None:
    result = normalize_url("HTTPS://WWW.Example.COM:443/A%20Page/?a=1#part")
    assert result.value == "https://www.example.com/A%20Page/?a=1"
    assert "fragment_removed" in result.reasons


def test_crawler_rejects_private_and_unconfirmed_targets() -> None:
    with pytest.raises(ValueError):
        validate_crawl_target("http://127.0.0.1/admin", frozenset({"127.0.0.1"}))
    with pytest.raises(ValueError):
        validate_crawl_target("https://other.example/", frozenset({"example.com"}))


def test_score_is_deterministic_explainable_and_not_a_prediction() -> None:
    score, evidence = opportunity_score(
        search_potential=80, business_value=90, relevance=100, confidence=70, urgency=60, effort=30
    )
    assert (
        score
        == opportunity_score(
            search_potential=80,
            business_value=90,
            relevance=100,
            confidence=70,
            urgency=60,
            effort=30,
        )[0]
    )
    assert evidence["effort"] == 30 and 0 <= score <= 100


def test_missing_is_not_zero() -> None:
    assert metric_value(None, "valid") == {"value": None, "state": "missing"}
    assert metric_value(0, "valid") == {"value": 0, "state": "valid"}


@pytest.mark.integration
def test_database_rejects_cross_organization_website_child(
    postgresql_test_url: str,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(postgresql_test_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO organizations
                                (id, name, slug, organization_type, status, timezone,
                                 default_currency)
                            VALUES
                                ('13160000-0000-4000-8000-000000000001',
                                 'SEO Isolation A', 'seo-isolation-a', 'test', 'active',
                                 'UTC', 'USD'),
                                ('13160000-0000-4000-8000-000000000002',
                                 'SEO Isolation B', 'seo-isolation-b', 'test', 'active',
                                 'UTC', 'USD')
                            """
                        )
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO seo_websites
                                (id, organization_id, key, name, canonical_origin,
                                 status, ownership_status)
                            VALUES
                                ('13160000-0000-4000-8000-000000000003',
                                 '13160000-0000-4000-8000-000000000001',
                                 'isolation-site', 'Isolation Site',
                                 'https://example.test', 'active', 'verified')
                            """
                        )
                    )
                    with pytest.raises(IntegrityError):
                        async with connection.begin_nested():
                            await connection.execute(
                                text(
                                    """
                                    INSERT INTO seo_pages
                                        (id, organization_id, website_id, normalized_url,
                                         observed_url, normalization_reasons,
                                         indexability, quality_status)
                                    VALUES
                                        ('13160000-0000-4000-8000-000000000004',
                                         '13160000-0000-4000-8000-000000000002',
                                         '13160000-0000-4000-8000-000000000003',
                                         'https://example.test/',
                                         'https://example.test/', '[]'::jsonb,
                                         'indexable', 'valid')
                                    """
                                )
                            )
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
