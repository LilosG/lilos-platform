"""SEO orchestration relies on the shared deterministic scoring contract."""

from apps.api.app.products.seo.service import opportunity_score


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
