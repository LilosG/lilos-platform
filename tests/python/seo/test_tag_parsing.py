"""The crawler must read a tag the way a browser does, not the way a regex hoped.

Every case here was a false SEO finding against a real client site. The previous
patterns required a fixed attribute order, quoted values, and no apostrophes:

    <meta[^>]+name=["']description["'][^>]+content=["']([^"']*)["']

An operator checked pages the crawl reported as missing a meta description,
found the description plainly present, and rightly stopped trusting the report.
"""

from apps.api.app.products.seo.crawl_engine import (
    _link_href,
    _meta_content,
    _tag_attributes,
    extract_page_signals,
)


class TestMetaContent:
    def test_reads_an_ordinary_description(self) -> None:
        html = '<meta name="description" content="A perfectly ordinary description">'
        assert _meta_content(html, "description") == "A perfectly ordinary description"

    def test_an_apostrophe_does_not_truncate_the_value(self) -> None:
        # Captured just "Carlsbad" before, silently corrupting the stored value
        # and everything downstream that reads it, including AI generation.
        html = '<meta name="description" content="Carlsbad\'s best plumber, open 24/7">'
        assert _meta_content(html, "description") == "Carlsbad's best plumber, open 24/7"

    def test_attribute_order_does_not_matter(self) -> None:
        # The false missing_meta_description. HTML attribute order is arbitrary.
        html = '<meta content="Roof repair in Vista, CA" name="description">'
        assert _meta_content(html, "description") == "Roof repair in Vista, CA"

    def test_unquoted_attribute_values_are_read(self) -> None:
        html = '<meta name=description content="Unquoted attribute name">'
        assert _meta_content(html, "description") == "Unquoted attribute name"

    def test_single_quoted_values_are_read(self) -> None:
        html = "<meta name='description' content='Single quoted value'>"
        assert _meta_content(html, "description") == "Single quoted value"

    def test_the_tag_may_wrap_across_lines(self) -> None:
        html = '<meta name="description"\n      content="Wrapped across lines">'
        assert _meta_content(html, "description") == "Wrapped across lines"

    def test_attribute_names_are_case_insensitive(self) -> None:
        html = '<meta NAME="Description" CONTENT="Case insensitive">'
        assert _meta_content(html, "description") == "Case insensitive"

    def test_an_unrelated_meta_tag_is_not_mistaken_for_the_description(self) -> None:
        html = (
            '<meta name="viewport" content="width=device-width">'
            '<meta property="og:description" content="the social one">'
        )
        assert _meta_content(html, "description") is None

    def test_a_genuinely_absent_description_is_still_absent(self) -> None:
        assert _meta_content("<html><head><title>x</title></head></html>", "description") is None

    def test_an_empty_description_is_empty_not_missing(self) -> None:
        # Distinct states: the tag is present and blank, which is an authoring
        # mistake worth reporting differently from having no tag at all.
        assert _meta_content('<meta name="description" content="">', "description") == ""


class TestRobotsDirectives:
    def test_noindex_is_seen_regardless_of_attribute_order(self) -> None:
        # The most consequential of the three. A page marked noindex this way
        # read as indexable, so it was crawled and ingested into knowledge.
        html = '<meta content="noindex, nofollow" name="robots">'
        assert _meta_content(html, "robots") == "noindex, nofollow"

    def test_conventional_order_still_works(self) -> None:
        assert _meta_content('<meta name="robots" content="noindex">', "robots") == "noindex"


class TestCanonicalLink:
    def test_href_before_rel(self) -> None:
        html = '<link href="https://example.invalid/a" rel="canonical">'
        assert _link_href(html, "canonical") == "https://example.invalid/a"

    def test_rel_is_a_token_list_not_a_string(self) -> None:
        html = '<link rel="canonical alternate" href="https://example.invalid/b">'
        assert _link_href(html, "canonical") == "https://example.invalid/b"

    def test_earlier_non_canonical_links_are_skipped(self) -> None:
        html = (
            '<link rel="stylesheet" href="/s.css">'
            '<link rel="icon" href="/f.ico">'
            '<link rel="canonical" href="https://example.invalid/c">'
        )
        assert _link_href(html, "canonical") == "https://example.invalid/c"

    def test_no_canonical_link_returns_none(self) -> None:
        assert _link_href('<link rel="stylesheet" href="/s.css">', "canonical") is None


class TestTagAttributes:
    def test_valueless_attributes_map_to_empty_string(self) -> None:
        assert _tag_attributes("data-astro-cid async")["async"] == ""

    def test_the_first_of_a_duplicated_attribute_wins(self) -> None:
        # Matches how browsers resolve repeated attributes.
        assert _tag_attributes('name="first" name="second"')["name"] == "first"


class TestSignalsEndToEnd:
    def test_a_page_with_a_reordered_description_is_not_flagged_as_missing(self) -> None:
        html = (
            "<html><head><title>Handyman</title>"
            '<meta content="Licensed handyman in Carlsbad" name="description">'
            "</head><body><h1>Handyman</h1><p>Text here.</p></body></html>"
        )
        signals = extract_page_signals(html, 200, "https://example.invalid/", [])

        assert signals["meta_description"] == "Licensed handyman in Carlsbad"
        assert "missing_meta_description" not in signals["technical_issues"]

    def test_a_page_genuinely_missing_a_description_is_still_flagged(self) -> None:
        html = "<html><head><title>t</title></head><body><h1>h</h1></body></html>"
        signals = extract_page_signals(html, 200, "https://example.invalid/", [])

        assert signals["meta_description"] is None
        assert "missing_meta_description" in signals["technical_issues"]
