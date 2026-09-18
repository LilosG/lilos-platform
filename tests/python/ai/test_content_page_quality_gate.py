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
            "knowledge": {
                "website_knowledge": [
                    {"url": "/menu/"},
                    {"url": "/brunch/"},
                    {"url": "/reservations/"},
                ]
            },
        },
    )

    assert "article_too_thin" in errors
    assert "article_heading_depth_missing" in errors
    assert "article_internal_links_missing" in errors
    assert "article_faq_depth_missing" in errors


def test_page_quality_floor_rejects_sub_thousand_word_marketing_copy() -> None:
    section = " ".join(f"detail{index}" for index in range(150))
    draft = "\n\n".join(
        f"## Bachelorette planning topic {heading}\n\n{section}" for heading in range(6)
    )
    payload = {
        "draft": draft,
        "meta_description": "Plan a bachelorette celebration in Little Italy, San Diego.",
        "seo_title": "Bachelorette Party Venue in Little Italy",
        "faqs": [
            {"question": "One?", "answer": " ".join(["useful"] * 20)},
            {"question": "Two?", "answer": " ".join(["useful"] * 20)},
            {"question": "Three?", "answer": " ".join(["useful"] * 20)},
        ],
    }
    errors = _validate_article_payload(
        payload,
        {
            "content_type": "page",
            "content_title": "Bachelorette Party Venue in Little Italy",
        },
    )
    assert "article_too_thin" in errors


def test_existing_canonical_target_is_not_rejected_as_duplicate_content() -> None:
    from apps.api.app.ai.providers import _find_existing_topic_overlap

    document = {
        "content_type": "page",
        "content_title": "Restaurants in Little Italy San Diego",
        "target_reference": "https://inlovewiththecoco.com/restaurants-little-italy",
        "knowledge": {
            "website_knowledge": [
                {
                    "url": "https://inlovewiththecoco.com/restaurants-little-italy/",
                    "title": "Restaurants in Little Italy San Diego",
                }
            ]
        },
    }

    assert _find_existing_topic_overlap(document) is None


def test_competing_page_with_same_topic_is_still_rejected() -> None:
    from apps.api.app.ai.providers import _find_existing_topic_overlap

    document = {
        "content_type": "page",
        "content_title": "Restaurants in Little Italy San Diego",
        "target_reference": "https://inlovewiththecoco.com/new-restaurants-page",
        "knowledge": {
            "website_knowledge": [
                {
                    "url": "https://inlovewiththecoco.com/restaurants-little-italy",
                    "title": "Restaurants in Little Italy San Diego",
                }
            ]
        },
    }

    assert (
        _find_existing_topic_overlap(document)
        == "https://inlovewiththecoco.com/restaurants-little-italy"
    )

