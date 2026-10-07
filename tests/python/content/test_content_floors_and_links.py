"""Quality floors per content type, internal-link rules, claim detection, inbound edits.

Pure unit tests: no database, no provider. A draft is built to an exact word count with the
same tokenizer the validator uses, so "one word under the floor fails, at the floor passes"
is asserted literally.
"""

from typing import Any

import pytest

from apps.api.app.ai.providers import (
    _article_quality_profile,
    _validate_article_payload,
    article_quality_summary,
)
from apps.api.app.products.content.claims import (
    ClaimStatus,
    detect_unbacked_specifics,
    merge_claims,
    normalize_claims,
    unresolved_claims,
)
from apps.api.app.products.content.link_validation import (
    LinkCode,
    PageKind,
    build_inbound_link_edit,
    build_inventory,
    classify_page_kind,
    validate_links,
)

from .draft_builder import FAQS, INVENTORY_ROWS, LINKS, build_draft

LONGFORM_TYPES = ["blog_post", "listicle", "guide", "roundup", "pillar"]
PAGE_TYPES = ["landing_page", "service_page", "location_page", "landing-page", "page"]


def payload(draft: str) -> dict[str, Any]:
    return {
        "draft": draft,
        "meta_description": "Where to watch Green Bay Packers games in San Diego.",
        "seo_title": "Packers Bar in San Diego",
        "faqs": FAQS,
    }


def document(content_type: str, **extra: Any) -> dict[str, Any]:
    return {
        "content_type": content_type,
        "content_title": "Packers game day topic San Diego",
        "link_inventory": INVENTORY_ROWS,
        **extra,
    }


# --- effective floors ----------------------------------------------------------------------


@pytest.mark.parametrize("content_type", [*LONGFORM_TYPES, *PAGE_TYPES])
def test_every_long_form_type_has_the_same_effective_floor(content_type: str) -> None:
    assert _article_quality_profile(content_type) == {
        "minimum_words": 1_400,
        "target_minimum_words": 1_700,
        "target_maximum_words": 2_300,
        "minimum_h2s": 7,
        "minimum_internal_links": 4,
        "minimum_faqs": 4,
    }


def test_floors_never_drop_below_what_they_were() -> None:
    previous_page = {"minimum_words": 1_100, "minimum_h2s": 6, "minimum_internal_links": 3}
    for content_type in PAGE_TYPES:
        profile = _article_quality_profile(content_type)
        assert all(profile[key] >= value for key, value in previous_page.items())


@pytest.mark.parametrize("content_type", [*LONGFORM_TYPES, *PAGE_TYPES])
def test_one_word_under_the_floor_is_rejected_and_the_floor_passes(content_type: str) -> None:
    floor = _article_quality_profile(content_type)["minimum_words"]
    under = _validate_article_payload(payload(build_draft(words=floor - 1)), document(content_type))
    at = _validate_article_payload(payload(build_draft(words=floor)), document(content_type))
    assert "article_too_thin" in under
    assert at == []


def test_too_few_headings_links_and_faqs_are_each_typed_failures() -> None:
    thin = payload(build_draft(words=1_500, links=LINKS[:2], h2s=7))
    thin["faqs"] = FAQS[:3]
    errors = _validate_article_payload(thin, document("listicle"))
    assert "article_internal_links_missing" in errors
    assert "article_faq_depth_missing" in errors
    short_sections = _validate_article_payload(
        payload(build_draft(words=1_500, h2s=6)), document("guide")
    )
    assert "article_heading_depth_missing" in short_sections


# --- internal links ------------------------------------------------------------------------


def test_a_link_to_a_page_that_does_not_exist_is_unverified() -> None:
    draft = build_draft(words=1_500, links=[*LINKS[:3], "[a page that was invented](/invented/)"])
    assert "article_internal_link_unverified" in _validate_article_payload(
        payload(draft), document("blog_post")
    )


def test_every_link_is_unverified_when_the_site_has_no_inventory() -> None:
    errors = _validate_article_payload(
        payload(build_draft(words=1_500)), {**document("blog_post"), "link_inventory": []}
    )
    assert "article_internal_link_unverified" in errors


def test_same_anchor_to_the_same_url_is_anchor_stuffing() -> None:
    links = [*LINKS, "[our full food and drink menu](/menu/)"]
    assert "article_anchor_stuffing" in _validate_article_payload(
        payload(build_draft(words=1_500, links=links)), document("blog_post")
    )


def test_one_url_linked_three_times_is_stuffing_even_with_varied_anchors() -> None:
    links = [
        *LINKS,
        "[see the weekend menu items](/menu/)",
        "[browse the lunch menu options](/menu/)",
    ]
    assert "article_anchor_stuffing" in _validate_article_payload(
        payload(build_draft(words=1_500, links=links)), document("blog_post")
    )


@pytest.mark.parametrize("anchor", ["click here", "Learn more", "here", "website"])
def test_generic_anchors_are_rejected(anchor: str) -> None:
    links = [*LINKS[:3], f"[{anchor}](/about/)"]
    assert "article_anchor_generic" in _validate_article_payload(
        payload(build_draft(words=1_500, links=links)), document("blog_post")
    )


def test_the_same_anchor_pointing_at_two_urls_is_ambiguous() -> None:
    links = [*LINKS[:3], "[our full food and drink menu](/about/)"]
    codes = validate_links(
        build_draft(words=1_500, links=links),
        build_inventory(INVENTORY_ROWS),
        minimum_links=4,
    )
    assert LinkCode.ANCHOR_AMBIGUOUS in codes


def test_a_draft_that_only_links_other_posts_misses_the_commercial_page() -> None:
    inventory = [
        *INVENTORY_ROWS[:3],
        {"url": "/blog/a-first-post/", "source": "content"},
        {"url": "/blog/a-second-post/", "source": "content"},
        {"url": "/blog/a-third-post/", "source": "content"},
        {"url": "/blog/a-fourth-post/", "source": "content"},
    ]
    links = [
        "[our first post about game day](/blog/a-first-post/)",
        "[the second post about wings](/blog/a-second-post/)",
        "[a third post about the stadium](/blog/a-third-post/)",
        "[our fourth post about tailgates](/blog/a-fourth-post/)",
    ]
    errors = _validate_article_payload(
        payload(build_draft(words=1_500, links=links)),
        {**document("blog_post"), "link_inventory": inventory},
    )
    assert "article_commercial_link_missing" in errors
    assert "article_internal_link_unverified" not in errors


def test_absolute_same_host_links_resolve_and_other_hosts_are_ignored() -> None:
    draft = (
        "[our full food and drink menu](https://www.missbs.example/menu/) and "
        "[a partner stadium guide](https://other.example/stadium/)"
    )
    codes = validate_links(
        draft,
        build_inventory(INVENTORY_ROWS, origin_host="missbs.example"),
        minimum_links=1,
        origin_host="missbs.example",
    )
    assert LinkCode.UNVERIFIED not in codes


def test_valid_links_pass_and_summary_reports_every_check() -> None:
    draft = payload(build_draft(words=1_500))
    document_ = document("listicle")
    assert _validate_article_payload(draft, document_) == []
    summary = article_quality_summary(draft, document_)
    assert summary is not None
    assert summary["word_count"] == 1_500
    assert summary["floor"]["minimum_words"] == 1_400
    assert all(check["passed"] for check in summary["checks"])
    assert {check["code"] for check in summary["checks"]} >= {
        "article_too_thin",
        "article_anchor_stuffing",
        "article_commercial_link_missing",
    }


def test_page_kinds_come_from_the_url_not_the_title() -> None:
    assert classify_page_kind("/menu") is PageKind.MENU
    assert classify_page_kind("/reservations") is PageKind.RESERVATION
    assert classify_page_kind("/services/water-heater-repair") is PageKind.SERVICE
    assert classify_page_kind("/locations/san-diego") is PageKind.LOCATION
    assert classify_page_kind("/blog/how-to-watch") is PageKind.CONTENT
    assert classify_page_kind("/about") is PageKind.OTHER


# --- claims --------------------------------------------------------------------------------


def test_invented_specifics_are_flagged_and_grounded_ones_are_not() -> None:
    draft = (
        "Miss B's is a Green Bay Packers bar in San Diego.\n\n"
        "The bar opened in 1987 and won an award-winning wings title.\n\n"
        "Call us at 619-555-0142 to reserve a table."
    )
    grounding = [
        "Operator prompt: Miss B's is a Green Bay Packers bar in San Diego.",
        "619-555-0142",
    ]
    flagged = detect_unbacked_specifics(draft, grounding)
    texts = [claim["text"] for claim in flagged]
    assert any("1987" in text for text in texts)
    assert not any("619-555-0142" in text for text in texts)
    assert not any("Green Bay Packers bar" in text for text in texts)
    assert all(claim["status"] == ClaimStatus.NEEDS_CONFIRMATION.value for claim in flagged)


def test_a_labelled_claim_must_quote_the_draft_and_unlabelled_means_unbacked() -> None:
    draft = "Miss B's serves Wisconsin cheese curds on game day."
    claims = normalize_claims(
        [
            {"text": "Miss B's serves Wisconsin cheese curds on game day.", "basis": "bogus"},
            {"text": "A sentence that is not in the draft.", "basis": "approved_fact"},
        ],
        draft,
    )
    assert len(claims) == 1
    assert claims[0]["status"] == ClaimStatus.NEEDS_CONFIRMATION.value
    merged = merge_claims(claims, [])
    assert len(unresolved_claims({"claims": merged})) == 1
    confirmed = [{**claims[0], "status": ClaimStatus.CONFIRMED.value}]
    assert unresolved_claims({"claims": confirmed}) == []


# --- inbound edits -------------------------------------------------------------------------


def test_inbound_edit_links_an_existing_phrase_and_keeps_the_rest_byte_for_byte() -> None:
    before = "Visit us for great Packers game day food.\n\nOur wings are popular."
    edit = build_inbound_link_edit(
        before, target_url="/blog/packers-game-day/", phrases=["Packers game day", "wings"]
    )
    assert edit is not None
    assert edit.anchor == "Packers game day"
    assert edit.before == before
    assert edit.after == (
        "Visit us for great [Packers game day](/blog/packers-game-day/) food.\n\n"
        "Our wings are popular."
    )


def test_inbound_edit_never_invents_an_anchor_or_double_links() -> None:
    before = "Visit us for lunch."
    assert (
        build_inbound_link_edit(before, target_url="/blog/x/", phrases=["Packers game day"]) is None
    )
    linked = "See [Packers game day](/blog/x/) tips."
    assert (
        build_inbound_link_edit(linked, target_url="/blog/x/", phrases=["Packers game day"]) is None
    )
    in_heading = "# Packers game day\n\nBody text."
    assert (
        build_inbound_link_edit(in_heading, target_url="/blog/x/", phrases=["Packers game day"])
        is None
    )
    single_word = "Our wings are popular."
    assert build_inbound_link_edit(single_word, target_url="/blog/x/", phrases=["wings"]) is None
