"""The committed file must carry frontmatter, or the client's site stops building.

Regression: the publish handler committed ``revision.body`` alone. The revision's
frontmatter -- a non-nullable JSONB column -- never reached the file. An Astro
content collection parses YAML frontmatter and validates it against the Zod schema
in src/content/config.ts, so a file without it fails `astro build` and takes the
client's Vercel deployment with it.
"""

from datetime import date, datetime

import pytest

from apps.api.app.products.content.file_format import (
    ContentFileFormatError,
    build_content_file,
    render_frontmatter,
)


def test_file_opens_with_a_frontmatter_block_then_the_body() -> None:
    output = build_content_file(
        "# Panel upgrades\n\nBody copy.\n",
        {"title": "Panel Upgrades", "description": "What a panel upgrade involves."},
    )

    assert output.startswith("---\n")
    head, _, rest = output[4:].partition("\n---\n")
    assert 'title: "Panel Upgrades"' in head
    assert 'description: "What a panel upgrade involves."' in head
    assert rest.lstrip("\n").startswith("# Panel upgrades")


def test_empty_frontmatter_is_refused() -> None:
    """An Astro collection schema cannot validate an empty block, so fail closed."""
    with pytest.raises(ContentFileFormatError) as caught:
        build_content_file("Body.", {})

    assert caught.value.safe_code == "CONTENT_FRONTMATTER_MISSING"


def test_body_that_already_has_frontmatter_is_refused() -> None:
    """Two blocks would make the second one page content."""
    with pytest.raises(ContentFileFormatError) as caught:
        build_content_file("---\ntitle: dupe\n---\n\nBody.", {"title": "Real"})

    assert caught.value.safe_code == "CONTENT_BODY_HAS_FRONTMATTER"


def test_strings_are_quoted_so_yaml_cannot_retype_them() -> None:
    """Unquoted yes/no/null/1.0 become booleans, nulls and numbers in YAML."""
    rendered = render_frontmatter(
        {"draft": "no", "version": "1.0", "answer": "yes", "blank": "null"}
    )

    assert 'draft: "no"' in rendered
    assert 'version: "1.0"' in rendered
    assert 'answer: "yes"' in rendered
    assert 'blank: "null"' in rendered


def test_quotes_and_newlines_in_values_are_escaped() -> None:
    rendered = render_frontmatter({"title": 'He said "hi"', "summary": "line one\nline two"})

    assert 'title: "He said \\"hi\\""' in rendered
    assert 'summary: "line one\\nline two"' in rendered
    # An unescaped newline would terminate the scalar and corrupt the block.
    assert rendered.count("\n") == 1


def test_booleans_and_numbers_keep_their_type() -> None:
    rendered = render_frontmatter({"draft": False, "order": 3})

    assert "draft: false" in rendered
    assert "order: 3" in rendered


def test_dates_are_rendered_iso8601() -> None:
    rendered = render_frontmatter(
        {"pubDate": date(2026, 8, 27), "updated": datetime(2026, 8, 27, 12, 30)}
    )

    assert 'pubDate: "2026-08-27"' in rendered
    assert 'updated: "2026-08-27T12:30:00"' in rendered


def test_lists_render_as_yaml_sequences() -> None:
    rendered = render_frontmatter({"tags": ["electrical", "panel upgrades"], "empty": []})

    assert '  - "electrical"' in rendered
    assert '  - "panel upgrades"' in rendered
    assert "empty: []" in rendered


def test_nested_mappings_render_indented() -> None:
    """Needed for Astro image objects and structured SEO fields."""
    rendered = render_frontmatter(
        {"image": {"url": "/img/panel.jpg", "alt": "A new panel"}, "seo": {"noindex": False}}
    )

    assert "image:\n" in rendered
    assert '  url: "/img/panel.jpg"' in rendered
    assert '  alt: "A new panel"' in rendered
    assert "  noindex: false" in rendered


def test_list_of_mappings_renders_for_faq_entries() -> None:
    """FAQ blocks are the common case: a sequence of question/answer mappings."""
    rendered = render_frontmatter(
        {
            "faqs": [
                {"question": "How long does it take?", "answer": "Usually one day."},
                {"question": "Is a permit needed?", "answer": "Often, yes."},
            ]
        }
    )

    lines = rendered.splitlines()
    assert lines[0] == "faqs:"
    assert lines[1].strip().startswith('- question: "How long does it take?"')
    assert 'answer: "Usually one day."' in rendered
    assert 'question: "Is a permit needed?"' in rendered


def test_unsupported_value_types_are_refused() -> None:
    with pytest.raises(ContentFileFormatError) as caught:
        render_frontmatter({"weird": object()})

    assert caught.value.safe_code == "CONTENT_FRONTMATTER_UNSUPPORTED_VALUE"


def test_invalid_keys_are_refused() -> None:
    for key in ("", "has:colon", "has\nnewline"):
        with pytest.raises(ContentFileFormatError) as caught:
            render_frontmatter({key: "value"})
        assert caught.value.safe_code == "CONTENT_FRONTMATTER_INVALID_KEY"


def test_output_is_deterministic_for_content_hashing() -> None:
    frontmatter = {"title": "A", "tags": ["x", "y"], "meta": {"a": 1}}

    assert build_content_file("Body.", frontmatter) == build_content_file("Body.", frontmatter)


def test_crlf_bodies_are_normalized() -> None:
    output = build_content_file("Line one.\r\nLine two.\r\n", {"title": "T"})

    assert "\r" not in output
    assert output.endswith("Line two.\n")
