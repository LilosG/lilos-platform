"""Focused deterministic tests for GBP AI post generation helpers."""

from apps.api.app.products.gbp.post_generation import GBPPostGenerationService


def test_target_url_prefers_relevant_service_page() -> None:
    knowledge = {
        "website_knowledge": [
            {
                "url": "https://example.com/ev-charger-installation/",
                "title": "EV Charger Installation",
                "h1": "Home EV Charger Installation",
            },
            {"url": "https://example.com/", "title": "Home"},
        ]
    }

    target = GBPPostGenerationService._select_target_url(
        {"websiteUri": "https://example.com/"},
        knowledge,
        "Customer review praised the EV charger installation",
    )

    assert target == "https://example.com/ev-charger-installation/"


def test_target_url_requires_positive_review_relevance() -> None:
    knowledge = {
        "website_knowledge": [
            {
                "url": "https://example.com/panel-upgrades/",
                "title": "Electrical Panel Upgrades",
                "h1": "Panel Upgrades",
            }
        ]
    }

    target = GBPPostGenerationService._select_target_url(
        {"websiteUri": "https://example.com/"},
        knowledge,
        "Customer review praised recessed kitchen lighting installation",
    )

    assert target is None


def test_clean_draft_is_bounded_and_uses_fallback() -> None:
    assert GBPPostGenerationService._clean_draft("", "Fallback copy") == "Fallback copy"
    assert len(GBPPostGenerationService._clean_draft("x" * 1400, "fallback")) == 1200
