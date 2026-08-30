"""Domain/origin correspondence — the rule that decides whether the website the
crawler knows about is the website the agency configured."""

import pytest

from apps.api.app.domains.matching import (
    WEBSITE_KEY_MAX_LENGTH,
    canonical_origin_for_domain,
    origin_host,
    origin_matches_domain,
    website_key_for_domain,
)


class TestOriginMatchesDomain:
    def test_exact_host_matches(self) -> None:
        assert origin_matches_domain("https://example.com", "example.com")

    def test_subdomain_belongs_to_its_parent(self) -> None:
        # The bare domain an agency types and the canonical origin a site
        # redirects to are routinely different by exactly this "www.".
        assert origin_matches_domain("https://www.example.com", "example.com")
        assert origin_matches_domain("https://shop.eu.example.com", "example.com")

    def test_a_domain_that_merely_ends_with_another_does_not_match(self) -> None:
        # "notexample.com" ends with "example.com" as a string. Matching on the
        # label boundary is the difference between correct and a cross-client
        # website association.
        assert not origin_matches_domain("https://notexample.com", "example.com")

    def test_parent_does_not_match_its_own_subdomain(self) -> None:
        assert not origin_matches_domain("https://example.com", "www.example.com")

    def test_case_and_trailing_dots_are_irrelevant(self) -> None:
        assert origin_matches_domain("https://WWW.Example.COM.", "example.com")
        assert origin_matches_domain("https://www.example.com", "Example.com.")

    def test_port_and_path_do_not_defeat_the_match(self) -> None:
        assert origin_matches_domain("https://www.example.com:8443/en/", "example.com")

    @pytest.mark.parametrize(
        "origin",
        ["", "not a url", "https://", "/relative/path", "http://[oops"],
    )
    def test_unusable_origins_do_not_match_rather_than_raising(self, origin: str) -> None:
        assert not origin_matches_domain(origin, "example.com")

    def test_an_empty_domain_never_matches(self) -> None:
        # Guards the degenerate case where an empty domain would otherwise turn
        # ``endswith(".")`` into a match against every host on the platform.
        assert not origin_matches_domain("https://example.com", "")
        assert not origin_matches_domain("https://example.com", ".")


class TestOriginHost:
    def test_returns_the_lowercase_host(self) -> None:
        assert origin_host("https://WWW.Example.com/path") == "www.example.com"

    def test_returns_none_when_there_is_no_host(self) -> None:
        assert origin_host("/just/a/path") is None
        assert origin_host("") is None


class TestCanonicalOrigin:
    def test_assumes_https(self) -> None:
        # Redirects resolve an HTTP-only site; defaulting to HTTP would
        # downgrade every correctly configured one.
        assert canonical_origin_for_domain("example.com") == "https://example.com"

    def test_normalizes_case_and_trailing_dot(self) -> None:
        assert canonical_origin_for_domain("Example.COM.") == "https://example.com"


class TestWebsiteKey:
    def test_is_derived_from_the_domain_and_stable(self) -> None:
        assert website_key_for_domain("inlovewiththecoco.com") == "inlovewiththecoco-com"
        assert website_key_for_domain("example.com") == website_key_for_domain("Example.com")

    def test_collapses_punctuation_runs(self) -> None:
        assert website_key_for_domain("my--weird..domain.co.uk") == "my-weird-domain-co-uk"

    def test_suffixes_deterministically_when_the_key_is_taken(self) -> None:
        taken = {"example-com"}
        assert website_key_for_domain("example.com", taken=taken) == "example-com-2"
        assert (
            website_key_for_domain("example.com", taken={"example-com", "example-com-2"})
            == "example-com-3"
        )

    def test_respects_the_column_length_including_the_suffix(self) -> None:
        domain = f"{'a' * 140}.com"
        key = website_key_for_domain(domain)
        assert len(key) <= WEBSITE_KEY_MAX_LENGTH

        suffixed = website_key_for_domain(domain, taken={key})
        assert len(suffixed) <= WEBSITE_KEY_MAX_LENGTH
        assert suffixed != key

    def test_raises_rather_than_reusing_a_key_it_cannot_make_unique(self) -> None:
        taken = {"example-com"} | {f"example-com-{index}" for index in range(2, 100)}
        with pytest.raises(ValueError):
            website_key_for_domain("example.com", taken=taken)
