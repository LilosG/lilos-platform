from apps.api.app.ai.providers import _is_article_content_type, _validate_article_payload


def test_page_and_landing_types_use_seo_quality_contract() -> None:
    assert _is_article_content_type("page") is True
    assert _is_article_content_type("landing") is True
    assert _is_article_content_type("landing_page") is True


def test_thin_generated_page_fails_before_editorial_review() -> None:
    payload = {
        "draft": (
            "## Why brunch here\n\n"
            "A short generic paragraph about brunch in Mission Beach.\n\n"
            "## What to expect\n\n"
            "Another short generic paragraph with little useful depth."
        ),
        "meta_description": "Brunch in Mission Beach.",
        "seo_title": "Best Brunch in Mission Beach",
        "faqs": [],
    }
    errors = _validate_article_payload(
        payload,
        {
            "content_type": "page",
            "content_title": "Best Brunch in San Diego, Mission Beach",
        },
    )

    assert "article_too_thin" in errors
    assert "article_heading_depth_missing" in errors
    assert "article_internal_links_missing" in errors
    assert "article_faq_depth_missing" in errors
