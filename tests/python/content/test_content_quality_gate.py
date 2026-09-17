"""Quality gates for AI-generated local SEO articles."""

from apps.api.app.ai.providers import (
    _build_prompt,
    _find_existing_topic_overlap,
    _validate_article_payload,
)


def _article_body(*, words_per_section: int = 150) -> str:
    headings = [
        "Happy Hour in Little Italy",
        "Little Italy Happy Hour Menu",
        "San Diego Weekday Happy Hour",
        "Rooftop Happy Hour Planning",
        "Little Italy Group Happy Hour",
        "Plan a San Diego Happy Hour Visit",
    ]
    sections: list[str] = []
    for index, heading in enumerate(headings):
        words = " ".join(f"detail{index}_{word}" for word in range(words_per_section))
        link = f" [Local resource {index}](/resource-{index}/)." if index < 3 else ""
        sections.append(f"## {heading}\n\n{words}.{link}")
    return "\n\n".join(sections)


def _payload(body: str) -> dict[str, object]:
    return {
        "draft": body,
        "meta_description": "Plan a source-backed happy hour visit in Little Italy, San Diego.",
        "seo_title": "Happy Hour in Little Italy San Diego",
        "faqs": [
            {"question": "When is happy hour?", "answer": "Check the current first-party hours."},
            {
                "question": "Should I reserve?",
                "answer": "Use the first-party reservation guidance.",
            },
            {"question": "Where is it?", "answer": "Use the source-backed location details."},
        ],
    }


def _input_document() -> dict[str, object]:
    return {
        "content_type": "blog",
        "content_title": "Happy Hour in Little Italy, San Diego | Coco Maya",
        "audience": "people planning a weekday happy hour",
        "intent": "find a useful local happy hour guide",
        "governed_facts": [
            {
                "fact_key": "business.address",
                "value": "1660 India St, San Diego, CA 92101",
                "authority": "client_approved",
            }
        ],
        "knowledge": {
            "website_knowledge": [
                {
                    "url": "/happy-hour/",
                    "title": "Happy Hour in Little Italy San Diego",
                    "h1": "Rooftop Happy Hour",
                    "body_text": "Weekday happy hour details and current first-party menu information.",
                }
            ]
        },
    }


def test_content_prompt_uses_source_knowledge_and_article_contract() -> None:
    prompt = _build_prompt("content.draft_revision", _input_document())

    assert "SOURCE-BACKED WEBSITE AND LOCAL KNOWLEDGE" in prompt
    assert '"url": "/happy-hour/"' in prompt
    assert "Do NOT put an H1 in the markdown body" in prompt
    assert "at least six descriptive H2 sections" in prompt
    assert "at least three natural internal markdown links" in prompt
    assert "three to six objects" in prompt


def test_topic_overlap_blocks_duplicate_local_article() -> None:
    document = _input_document()
    document["knowledge"] = {
        "website_knowledge": [
            {
                "url": "/blog/best-happy-hour-little-italy/",
                "title": "Happy Hour in Little Italy: Coco Maya's Weekday Menu",
            }
        ]
    }

    assert _find_existing_topic_overlap(document) == "/blog/best-happy-hour-little-italy/"


def test_thin_article_fails_quality_floor() -> None:
    errors = _validate_article_payload(
        {
            "draft": "A very short generic paragraph with no structure or links.",
            "meta_description": "Short description.",
            "seo_title": "Happy Hour",
            "faqs": [],
        },
        _input_document(),
    )

    assert "article_too_thin" in errors
    assert "article_heading_depth_missing" in errors
    assert "article_internal_links_missing" in errors
    assert "article_faq_depth_missing" in errors


def test_body_h1_is_rejected_for_template_rendered_articles() -> None:
    errors = _validate_article_payload(
        _payload("# Duplicate H1\n\n" + _article_body()),
        _input_document(),
    )

    assert "article_body_h1_not_allowed" in errors


def test_substantive_article_passes_quality_floor() -> None:
    errors = _validate_article_payload(_payload(_article_body()), _input_document())

    assert errors == []
