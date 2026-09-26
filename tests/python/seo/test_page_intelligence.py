"""Deterministic Page Intelligence comparison and bounded evidence tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from apps.api.app.products.seo.models import SEOCrawlPageObservation
from apps.api.app.products.seo.page_identity import PageResolver
from apps.api.app.products.seo.page_intelligence import _change_summary, _sitemap_evidence


def _snapshot(**overrides: object) -> SEOCrawlPageObservation:
    values: dict[str, object] = {
        "observed_at": datetime(2026, 9, 25, tzinfo=UTC),
        "http_status": 200,
        "content_type": "text/html",
        "title": "Title",
        "meta_description": "Description",
        "h1": "Heading",
        "canonical_url": None,
        "robots_directives": [],
        "internal_links": [],
        "external_links": [],
        "word_count": 12,
        "structured_data_present": False,
        "content_hash": "a" * 64,
        "indexability": "indexable",
        "technical_issues": [],
        "crawl_depth": 0,
        "redirect_destination": None,
        "quality_status": "clean",
    }
    values.update(overrides)
    return cast(SEOCrawlPageObservation, SimpleNamespace(**values))


def test_page_change_is_first_observation_without_comparable_history() -> None:
    result = _change_summary(_snapshot(), None)
    assert result["state"] == "first_observation"
    assert result["comparable_history_available"] is False
    assert "fields" not in result


def test_page_change_reports_stored_hash_and_bounded_link_list_delta() -> None:
    previous = _snapshot(internal_links=[f"https://example.test/old-{i}" for i in range(30)])
    latest = _snapshot(
        content_hash="b" * 64,
        internal_links=[f"https://example.test/new-{i}" for i in range(30)],
    )
    result = _change_summary(latest, previous)
    assert result["state"] == "changed"
    assert result["comparable_history_available"] is True
    fields = cast(dict[str, object], result["fields"])
    assert fields["content_hash"] == {"previous": "a" * 64, "current": "b" * 64}
    link_delta = cast(dict[str, object], fields["internal_links"])
    assert link_delta["added_count"] == 30
    assert link_delta["removed_count"] == 30
    assert link_delta["sample_truncated"] is True
    assert len(cast(list[str], link_delta["added_sample"])) == 20
    assert "body_text" not in fields


def test_page_change_reports_no_change_for_equal_stored_facts() -> None:
    result = _change_summary(_snapshot(), _snapshot())
    assert result["state"] == "no_change"
    assert result["comparable_history_available"] is True


def test_page_change_unavailable_has_no_comparable_history() -> None:
    result = _change_summary(None, None)
    assert result["state"] == "unavailable"
    assert result["comparable_history_available"] is False


def test_page_specific_sitemap_facts_are_from_the_exact_run() -> None:
    run_id = uuid4()
    run = SimpleNamespace(
        id=run_id,
        safe_result={
            "page_evidence_version": "crawl_page.v1",
            "sitemap_page_urls": ["https://example.test/listed"],
            "sitemap_not_reached": [],
            "crawled_not_in_sitemap": ["https://example.test/missing"],
            "sitemap_non_indexable": ["https://example.test/listed"],
        },
    )
    listed = _sitemap_evidence(
        cast(Any, SimpleNamespace(normalized_url="https://example.test/listed")), cast(Any, run)
    )
    missing = _sitemap_evidence(
        cast(Any, SimpleNamespace(normalized_url="https://example.test/missing")), cast(Any, run)
    )
    assert listed["crawl_run_id"] == missing["crawl_run_id"] == run_id
    assert listed["availability"] == "observed" and listed["listed"] is True
    assert listed["sitemap_non_indexable"] is True
    assert missing["listed"] is False and missing["crawled_not_in_sitemap"] is True
    assert (
        _sitemap_evidence(
            cast(Any, SimpleNamespace(normalized_url="https://example.test/listed")),
            cast(Any, SimpleNamespace(id=uuid4(), safe_result={})),
        )["availability"]
        == "unavailable"
    )


def test_internal_link_target_resolution_never_maps_alias_to_source() -> None:
    old_id, parameterized_id, target_id = uuid4(), uuid4(), uuid4()
    old = SimpleNamespace(
        id=old_id,
        normalized_url="https://example.test/old",
        canonical_url=None,
        redirect_destination="https://example.test/new",
    )
    parameterized = SimpleNamespace(
        id=parameterized_id,
        normalized_url="https://example.test/service?x=1",
        canonical_url="https://example.test/service",
        redirect_destination=None,
    )
    resolver = PageResolver(cast(Any, [old, parameterized]))
    assert resolver.resolve("https://example.test/new").page_id is None
    assert resolver.resolve("https://example.test/service").page_id is None
    assert resolver.resolve("https://example.test/service?x=1").page_id == parameterized_id
    assert resolver.resolve("http://example.test/old").page_id is None
    assert resolver.resolve("https://www.example.test/old").page_id is None
    assert resolver.resolve("https://example.test/old/").page_id is None
    target = SimpleNamespace(
        id=target_id,
        normalized_url="https://example.test/new",
        canonical_url=None,
        redirect_destination=None,
    )
    assert (
        PageResolver(cast(Any, [old, parameterized, target]))
        .resolve("https://example.test/new")
        .page_id
        == target_id
    )
