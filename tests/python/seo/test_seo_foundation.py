import pytest

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
