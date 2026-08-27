"""Generated revisions must satisfy the client collection schema.

Drafting previously produced `frontmatter={"title": item.title}` and nothing else.
Every client Astro blog schema declares `description` as a required `z.string()`,
so those revisions could not build even once frontmatter was serialized correctly.
"""

from apps.api.app.products.content.file_format import missing_required_frontmatter
from apps.api.app.products.content.service import (
    META_DESCRIPTION_MAXIMUM,
    build_publishable_frontmatter,
)


def test_model_supplied_description_is_used() -> None:
    frontmatter = build_publishable_frontmatter(
        title="Panel Upgrades in Carlsbad",
        ai_output={"meta_description": "When a 200-amp panel upgrade makes sense."},
        body="# Heading\n\nBody copy.",
    )

    assert frontmatter["description"] == "When a 200-amp panel upgrade makes sense."
    assert missing_required_frontmatter(frontmatter) == ()


def test_description_falls_back_to_body_prose_not_headings() -> None:
    """A missing description must not block publication, and must not be markdown."""
    frontmatter = build_publishable_frontmatter(
        title="Panel Upgrades",
        ai_output={},
        body="# Panel Upgrades\n\n- bullet\n\nMany older homes were wired for 100-amp service.",
    )

    description = str(frontmatter["description"])
    assert description.startswith("Many older homes")
    assert "#" not in description
    assert "bullet" not in description
    assert missing_required_frontmatter(frontmatter) == ()


def test_description_falls_back_to_title_when_there_is_no_prose() -> None:
    frontmatter = build_publishable_frontmatter(
        title="Panel Upgrades", ai_output=None, body="# Only a heading\n"
    )

    assert frontmatter["description"] == "Panel Upgrades"
    assert missing_required_frontmatter(frontmatter) == ()


def test_long_descriptions_are_clipped_at_a_word_boundary() -> None:
    frontmatter = build_publishable_frontmatter(
        title="T",
        ai_output={"meta_description": "word " * 80},
        body="Body.",
    )

    description = str(frontmatter["description"])
    assert len(description) <= META_DESCRIPTION_MAXIMUM + 1  # trailing ellipsis
    assert description.endswith("…")
    assert not description.rstrip("…").endswith(" ")


def test_whitespace_is_collapsed() -> None:
    frontmatter = build_publishable_frontmatter(
        title="T",
        ai_output={"meta_description": "  spread   over\nlines  "},
        body="Body.",
    )

    assert frontmatter["description"] == "spread over lines"
