"""Per-client Astro collection contracts.

Field names and constraints below were read from the live client repositories on
2026-08-27. Emitting a key a collection schema does not declare, or a value
outside a z.enum, fails `astro build` and breaks that client's deployment on
merge -- so a shared field set is not safe and this mapping exists.
"""

from datetime import date

import pytest

from apps.api.app.products.content.frontmatter_contract import (
    FrontmatterContract,
    FrontmatterContractError,
)

# wheylandelectric-final-2.0: date?, publishDate?, faqs[{question,answer}]
WHEYLAND = {
    "field_names": {"publish_date": "date", "related_services": "relatedServices"},
    "required": ["title", "description"],
}

# carlsbadfixit-final: pubDate?, serviceAreas is z.array(z.enum(serviceAreas))
CARLSBAD_FIXIT = {
    "field_names": {"publish_date": "pubDate", "service_areas": "serviceAreas"},
    "required": ["title", "description"],
    "enums": {"serviceAreas": ["carlsbad", "oceanside", "vista"]},
}

# tamarackrestoration-final-2.0: publishDate is a REQUIRED z.date(), category enum
TAMARACK = {
    "field_names": {"publish_date": "publishDate", "related_services": "relatedServices"},
    "required": ["title", "description", "publishDate", "category"],
    "date_format": "date",
    "enums": {"category": ["water-damage", "mold", "fire"]},
}

# kelari-party-rentals-final: publishDate is a REQUIRED z.string()
KELARI = {
    "field_names": {"publish_date": "publishDate"},
    "required": ["title", "description", "publishDate"],
    "date_format": "string",
}

# sage-therapy-center: FAQ keys are q/a
SAGE = {"faq_question_key": "q", "faq_answer_key": "a"}

CANONICAL = {
    "title": "Panel Upgrades in Carlsbad",
    "description": "When a 200-amp upgrade makes sense.",
    "publish_date": date(2026, 8, 27),
    "faqs": [{"question": "How long?", "answer": "Usually one day."}],
    "related_services": ["electrical-panel-upgrades"],
    "service_areas": ["carlsbad", "encinitas"],
    "category": "water-damage",
}


def test_no_contract_falls_back_to_the_universal_floor() -> None:
    contract = FrontmatterContract.from_document({})

    assert contract.required == ("title", "description")
    assert contract.target_key("publish_date") == "publish_date"


def test_wheyland_date_field_is_named_date() -> None:
    rendered = FrontmatterContract.from_document(WHEYLAND).render(CANONICAL)

    assert rendered["date"] == "2026-08-27"
    assert "publishDate" not in rendered
    assert rendered["relatedServices"] == ["electrical-panel-upgrades"]


def test_carlsbad_fixit_date_field_is_named_pubdate() -> None:
    rendered = FrontmatterContract.from_document(CARLSBAD_FIXIT).render(CANONICAL)

    assert rendered["pubDate"] == "2026-08-27"
    assert "date" not in rendered


def test_enum_constrained_values_outside_the_set_are_dropped() -> None:
    """carlsbadfixit constrains serviceAreas; 'encinitas' is not a member."""
    rendered = FrontmatterContract.from_document(CARLSBAD_FIXIT).render(CANONICAL)

    assert rendered["serviceAreas"] == ["carlsbad"]


def test_unconstrained_target_keeps_every_service_area() -> None:
    rendered = FrontmatterContract.from_document(WHEYLAND).render(CANONICAL)

    assert rendered["service_areas"] == ["carlsbad", "encinitas"]


def test_tamarack_requires_publish_date_and_category() -> None:
    contract = FrontmatterContract.from_document(TAMARACK)

    rendered = contract.render(CANONICAL)
    assert contract.missing_required(rendered) == ()

    without_category = {k: v for k, v in CANONICAL.items() if k != "category"}
    assert contract.missing_required(contract.render(without_category)) == ("category",)


def test_category_outside_the_enum_surfaces_as_missing_required() -> None:
    """Dropping an invalid enum member must not silently publish without it."""
    contract = FrontmatterContract.from_document(TAMARACK)

    rendered = contract.render({**CANONICAL, "category": "not-a-real-category"})

    assert "category" not in rendered
    assert contract.missing_required(rendered) == ("category",)


def test_kelari_publish_date_is_required() -> None:
    contract = FrontmatterContract.from_document(KELARI)

    without_date = {k: v for k, v in CANONICAL.items() if k != "publish_date"}
    assert contract.missing_required(contract.render(without_date)) == ("publishDate",)


def test_sage_therapy_faq_keys_are_q_and_a() -> None:
    rendered = FrontmatterContract.from_document(SAGE).render(CANONICAL)

    assert rendered["faqs"] == [{"q": "How long?", "a": "Usually one day."}]


def test_default_faq_keys_are_question_and_answer() -> None:
    rendered = FrontmatterContract.from_document(WHEYLAND).render(CANONICAL)

    assert rendered["faqs"] == [{"question": "How long?", "answer": "Usually one day."}]


def test_incomplete_faq_entries_are_dropped() -> None:
    rendered = FrontmatterContract.from_document({}).render(
        {**CANONICAL, "faqs": [{"question": "Only a question"}, {"answer": "Only an answer"}]}
    )

    assert "faqs" not in rendered


def test_blank_values_are_not_emitted() -> None:
    contract = FrontmatterContract.from_document({})

    rendered = contract.render({"title": "T", "description": "   "})

    assert "description" not in rendered
    assert contract.missing_required(rendered) == ("description",)


def test_defaults_do_not_override_generated_values() -> None:
    contract = FrontmatterContract.from_document({"defaults": {"draft": False, "title": "Ignored"}})

    rendered = contract.render(CANONICAL)

    assert rendered["draft"] is False
    assert rendered["title"] == "Panel Upgrades in Carlsbad"


def test_invalid_date_format_is_rejected() -> None:
    with pytest.raises(FrontmatterContractError) as caught:
        FrontmatterContract.from_document({"date_format": "epoch"})

    assert caught.value.safe_code == "CONTENT_CONTRACT_INVALID"


def test_rendered_frontmatter_survives_the_file_writer() -> None:
    """The contract's output must be publishable, not just well-shaped."""
    from apps.api.app.products.content.file_format import build_content_file

    rendered = FrontmatterContract.from_document(TAMARACK).render(CANONICAL)
    output = build_content_file("Body copy.\n", rendered)

    assert output.startswith("---\n")
    assert 'publishDate: "2026-08-27"' in output
    assert 'category: "water-damage"' in output
    assert '  - question: "How long?"' in output
