"""Quality gates for AI-generated local SEO articles."""

from uuid import uuid4

from apps.api.app.products.content.service import validate_content


def _article_body(*, words: int = 1100, h2_count: int = 6, link_count: int = 3) -> str:
    sections: list[str] = []
    words_per_section = max(1, words // h2_count)
    for index in range(h2_count):
        section_words = " ".join(f"local{index}_{word}" for word in range(words_per_section))
        links = ""
        if index < link_count:
            links = f" [Helpful local resource {index}](/local-resource-{index}/)."
        sections.append(f"## Local Section {index + 1}\n\n{section_words}.{links}")
    return "\n\n".join(sections)


def test_ai_blog_rejects_thin_unstructured_unlinked_content() -> None:
    validation = validate_content(
        "Happy hour copy with almost no depth and no useful structure.",
        {"title": "Happy Hour in Little Italy", "description": "A local guide."},
        [],
        [uuid4()],
        content_type="blog",
        created_by_type="ai",
    )

    assert validation["valid"] is False
    assert "article_too_thin" in validation["errors"]
    assert "article_heading_depth_missing" in validation["errors"]
    assert "article_internal_links_missing" in validation["errors"]


def test_ai_blog_rejects_body_h1_because_template_owns_article_h1() -> None:
    body = "# Duplicate H1\n\n" + _article_body()
    validation = validate_content(
        body,
        {"title": "Local Guide", "description": "A source-backed local guide."},
        [],
        [uuid4()],
        content_type="blog",
        created_by_type="ai",
    )

    assert validation["valid"] is False
    assert "article_body_h1_not_allowed" in validation["errors"]


def test_ai_blog_rejects_missing_structured_faqs() -> None:
    validation = validate_content(
        _article_body(),
        {"title": "Local Guide", "description": "A source-backed local guide."},
        [],
        [uuid4()],
        content_type="blog",
        created_by_type="ai",
    )

    assert validation["valid"] is False
    assert "article_faq_depth_missing" in validation["errors"]


def test_ai_blog_accepts_substantive_structured_linked_article() -> None:
    validation = validate_content(
        _article_body(),
        {
            "title": "Local Guide",
            "description": "A source-backed local guide.",
            "faqs": [
                {"question": "What should I know?", "answer": "Use the source-backed local details."},
                {"question": "When should I visit?", "answer": "Check the current published hours."},
                {"question": "How should I plan?", "answer": "Use the linked first-party resources."},
            ],
        },
        [],
        [uuid4()],
        content_type="blog",
        created_by_type="ai",
    )

    assert validation == {"valid": True, "errors": []}


def test_manual_revision_keeps_existing_policy_validation_only() -> None:
    validation = validate_content(
        "Short operator-authored correction.",
        {"title": "Correction", "description": "A correction."},
        [],
        [uuid4()],
        content_type="blog",
        created_by_type="user",
    )

    assert validation == {"valid": True, "errors": []}
