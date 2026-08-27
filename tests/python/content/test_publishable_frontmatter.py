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


def test_canonical_field_names_are_used_not_client_names() -> None:
    """Revisions store LILOs' names; the target's contract renames them at publish."""
    frontmatter = build_publishable_frontmatter(
        title="Panel Upgrades",
        ai_output={
            "meta_description": "A description.",
            "faqs": [{"question": "How long?", "answer": "One day."}],
            "related_services": ["panel-upgrades"],
            "service_areas": ["carlsbad"],
            "category": "electrical",
        },
        body="Body.",
    )

    assert "publish_date" in frontmatter
    assert "related_services" in frontmatter
    assert "service_areas" in frontmatter
    # Client-specific spellings must not appear at this stage.
    for client_name in ("pubDate", "publishDate", "relatedServices", "serviceAreas"):
        assert client_name not in frontmatter


def test_faqs_are_bounded_and_incomplete_pairs_dropped() -> None:
    from apps.api.app.products.content.service import MAXIMUM_FAQS

    frontmatter = build_publishable_frontmatter(
        title="T",
        ai_output={
            "meta_description": "D",
            "faqs": [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(12)]
            + [{"question": "No answer"}, {"answer": "No question"}],
        },
        body="Body.",
    )

    faqs = frontmatter["faqs"]
    assert isinstance(faqs, list)
    assert len(faqs) == MAXIMUM_FAQS
    assert all(set(entry) == {"question", "answer"} for entry in faqs)


def test_long_faq_text_is_clipped() -> None:
    from apps.api.app.products.content.service import (
        FAQ_ANSWER_MAXIMUM,
        FAQ_QUESTION_MAXIMUM,
    )

    frontmatter = build_publishable_frontmatter(
        title="T",
        ai_output={
            "meta_description": "D",
            "faqs": [{"question": "q" * 500, "answer": "a" * 2000}],
        },
        body="Body.",
    )

    entry = frontmatter["faqs"][0]  # type: ignore[index]
    assert len(entry["question"]) <= FAQ_QUESTION_MAXIMUM
    assert len(entry["answer"]) <= FAQ_ANSWER_MAXIMUM


def test_term_lists_are_deduplicated_case_insensitively() -> None:
    frontmatter = build_publishable_frontmatter(
        title="T",
        ai_output={
            "meta_description": "D",
            "related_services": ["Panel-Upgrades", "panel-upgrades", "ev-chargers"],
        },
        body="Body.",
    )

    assert frontmatter["related_services"] == ["Panel-Upgrades", "ev-chargers"]


def test_absent_optional_fields_are_omitted_not_blank() -> None:
    """An empty list would be published as `[]` and read as an intentional value."""
    frontmatter = build_publishable_frontmatter(
        title="T", ai_output={"meta_description": "D"}, body="Body."
    )

    for optional in ("faqs", "related_services", "service_areas", "tags", "category"):
        assert optional not in frontmatter


def test_publish_date_defaults_to_today_and_is_overridable() -> None:
    from datetime import date

    default = build_publishable_frontmatter(title="T", ai_output={}, body="Body.")
    assert isinstance(default["publish_date"], str)

    explicit = build_publishable_frontmatter(
        title="T", ai_output={}, body="Body.", publish_date=date(2026, 3, 24)
    )
    assert explicit["publish_date"] == "2026-03-24"


def test_generated_frontmatter_maps_through_every_client_contract() -> None:
    """End to end: generation -> contract mapping -> publishable file."""
    from apps.api.app.products.content.file_format import build_content_file
    from apps.api.app.products.content.frontmatter_contract import FrontmatterContract

    generated = build_publishable_frontmatter(
        title="Panel Upgrades in Carlsbad",
        ai_output={
            "meta_description": "When a 200-amp upgrade makes sense.",
            "faqs": [{"question": "How long?", "answer": "Usually one day."}],
            "related_services": ["electrical-panel-upgrades"],
            "category": "water-damage",
        },
        body="# Panel Upgrades\n\nBody copy.\n",
    )

    # wheylandelectric: date field is `date`
    wheyland = FrontmatterContract.from_document(
        {"field_names": {"publish_date": "date", "related_services": "relatedServices"}}
    )
    rendered = wheyland.render(generated)
    assert wheyland.missing_required(rendered) == ()
    assert "date" in rendered and "relatedServices" in rendered
    assert 'date: "' in build_content_file("Body.\n", rendered)

    # kelari: publishDate is a required z.string()
    kelari = FrontmatterContract.from_document(
        {
            "field_names": {"publish_date": "publishDate"},
            "required": ["title", "description", "publishDate"],
            "date_format": "string",
        }
    )
    rendered = kelari.render(generated)
    assert kelari.missing_required(rendered) == ()

    # sage-therapy-center: FAQ keys are q/a
    sage = FrontmatterContract.from_document({"faq_question_key": "q", "faq_answer_key": "a"})
    assert sage.render(generated)["faqs"] == [{"q": "How long?", "a": "Usually one day."}]
