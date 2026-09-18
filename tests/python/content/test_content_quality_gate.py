"""Quality gates for AI-generated local SEO articles."""

from apps.api.app.ai.providers import (
    _build_prompt,
    _find_existing_topic_overlap,
    _validate_article_payload,
)


def _article_body(*, words_per_section: int = 220) -> str:
    headings = [
        "Happy Hour in Little Italy",
        "Little Italy Happy Hour Menu",
        "San Diego Weekday Happy Hour",
        "Rooftop Happy Hour Planning",
        "Little Italy Group Happy Hour",
        "Plan a San Diego Happy Hour Visit",
        "Questions to Ask Before You Go",
    ]
    sections: list[str] = []
    for index, heading in enumerate(headings):
        words = " ".join(f"detail{index}_{word}" for word in range(words_per_section))
        link = f" [Local resource {index}](/resource-{index}/)." if index < 4 else ""
        sections.append(f"## {heading}\n\n{words}.{link}")
    return "\n\n".join(sections)


def _payload(body: str) -> dict[str, object]:
    return {
        "draft": body,
        "meta_description": "Plan a source-backed happy hour visit in Little Italy, San Diego.",
        "seo_title": "Happy Hour in Little Italy San Diego",
        "faqs": [
            {
                "question": "When is happy hour?",
                "answer": "Current happy hour timing should be confirmed from the first-party hours and menu before visiting because operating details can change.",
            },
            {
                "question": "Should I reserve?",
                "answer": "Use the first-party reservation guidance for the current booking process. Larger groups should review the venue's published planning information before arriving.",
            },
            {
                "question": "Where is it?",
                "answer": "Use the source-backed address and location details when planning the visit. Confirm directions from the first-party site before traveling.",
            },
            {
                "question": "What should a group plan for?",
                "answer": "Review the current menu, hours, and group guidance together so the visit matches the occasion. Use only the venue's published details for final planning.",
            },
        ],
    }


def _input_document() -> dict[str, object]:
    body_text = "Weekday happy hour details and current first-party menu information."
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
                    "url": f"/resource-{index}/",
                    "title": f"Happy Hour Planning Resource {index}",
                    "h1": f"Local Resource {index}",
                    "body_text": body_text,
                }
                for index in range(4)
            ]
        },
    }


def test_content_prompt_uses_source_knowledge_and_article_contract() -> None:
    prompt = _build_prompt("content.draft_revision", _input_document())

    assert "SOURCE-BACKED WEBSITE AND LOCAL KNOWLEDGE" in prompt
    assert '"url": "/resource-0/"' in prompt
    assert "Do NOT put an H1 in the markdown body" in prompt
    assert "1,700–2,300 substantive words" in prompt
    assert "at least 7 descriptive H2 sections" in prompt
    assert "up to 4 relevant first-party URLs" in prompt
    assert "4 to six FAQs" in prompt


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


def test_multiple_stub_sections_fail_quality_floor() -> None:
    body = _article_body()
    body += "\n\n## Extra Thin Section\n\nToo short to help."
    body += "\n\n## Another Thin Section\n\nAlso too short to help."
    errors = _validate_article_payload(_payload(body), _input_document())
    assert "article_sections_too_thin" in errors


def test_unverified_internal_link_fails_quality_floor() -> None:
    body = _article_body().replace("/resource-0/", "/invented-url/")
    errors = _validate_article_payload(_payload(body), _input_document())
    assert "article_internal_link_unverified" in errors


def test_body_h1_is_rejected_for_template_rendered_articles() -> None:
    errors = _validate_article_payload(
        _payload("# Duplicate H1\n\n" + _article_body()),
        _input_document(),
    )

    assert "article_body_h1_not_allowed" in errors


def test_substantive_article_passes_quality_floor() -> None:
    errors = _validate_article_payload(_payload(_article_body()), _input_document())

    assert errors == []
