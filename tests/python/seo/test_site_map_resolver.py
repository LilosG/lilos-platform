"""URL->file->field resolution for all three site-change source types.

Fixtures are modeled on real client repo shapes: `keystatic_json` on
`LilosG/coco-maya` (singleton-wrapped) and `LilosG/louisiana-purchase`
(top-level, no wrapper); `frontmatter` on MDX blog posts; `astro_code` on
the home-services pattern (no Keystatic layer, page copy lives directly in
`.astro` frontmatter and `src/lib/seo.ts`).
"""

import pytest

from apps.api.app.products.seo.change_set import SiteChangeField
from apps.api.app.products.seo.errors import SEOSiteMappingRequiredError
from apps.api.app.products.seo.site_map_resolver import (
    AstroCodeLocator,
    FrontmatterLocator,
    KeystaticJsonLocator,
    apply_change,
    normalize_url_path,
    page_map_from_contract,
    resolve_current_value,
    resolve_entry,
)

# A trimmed excerpt of the real singleton shape at
# LilosG/coco-maya:src/content/brunchPage.json.
COCO_MAYA_BRUNCH_JSON = (
    '{ "singleton": { "breadcrumbLabel": "Brunch", "seo": { '
    '"title": "Best Daily Brunch in Little Italy San Diego | Coco Maya", '
    '"descriptionTemplate": "Best brunch in Little Italy, San Diego at Coco Maya. '
    'Served daily until 3PM.", "image": "/images/food-tacos-patio.jpg" } } }'
)

# The real top-level (unwrapped) shape at
# LilosG/louisiana-purchase:src/content/brunchPage/page.json.
LOUISIANA_PURCHASE_BRUNCH_JSON = (
    '{"menuLink": {"label": "View the Full Menu", "href": "/menu"}, '
    '"seo": {"title": "Weekend Creole Brunch in North Park | Louisiana Purchase", '
    '"description": "Weekend Creole brunch at Louisiana Purchase in North Park."}}'
)

MDX_BLOG_POST = """---
title: "Best Brunch Spots in San Diego"
seoTitle: "Best Brunch San Diego | Coco Maya"
description: "Our guide to the best brunch spots in San Diego."
---

# Best Brunch Spots

Body content here.
"""

ASTRO_HOMEPAGE = """---
import PageLayout from '../layouts/PageLayout.astro';
import { homePageMeta } from '../lib/seo';

const meta = homePageMeta();
---
<PageLayout meta={meta}>
</PageLayout>
"""

SEO_TS = """
export function homePageMeta() {
  return {
    title: "Wheyland Electric | Licensed Electrician",
    description: "Licensed electrician serving North County San Diego.",
  };
}
"""


def test_resolves_coco_maya_singleton_wrapped_seo_title() -> None:
    files = {"src/content/brunchPage.json": COCO_MAYA_BRUNCH_JSON}
    locator = KeystaticJsonLocator(
        file_path="src/content/brunchPage.json",
        json_pointer=("singleton", "seo", "title"),
    )
    assert (
        resolve_current_value(files, locator)
        == "Best Daily Brunch in Little Italy San Diego | Coco Maya"
    )


def test_applies_minimal_diff_edit_to_coco_maya_seo_title() -> None:
    files = {"src/content/brunchPage.json": COCO_MAYA_BRUNCH_JSON}
    locator = KeystaticJsonLocator(
        file_path="src/content/brunchPage.json",
        json_pointer=("singleton", "seo", "title"),
    )
    current = resolve_current_value(files, locator)
    updated = apply_change(files, locator, current, "New Brunch Title | Coco Maya")
    assert '"title": "New Brunch Title | Coco Maya"' in updated["src/content/brunchPage.json"]
    # Every other field is untouched -- a minimal diff, not a reformat.
    assert '"breadcrumbLabel": "Brunch"' in updated["src/content/brunchPage.json"]
    assert (
        '"descriptionTemplate": "Best brunch in Little Italy, San Diego at Coco Maya. '
        'Served daily until 3PM."' in updated["src/content/brunchPage.json"]
    )
    assert files["src/content/brunchPage.json"] == COCO_MAYA_BRUNCH_JSON  # input untouched


def test_applies_edit_to_coco_maya_meta_description() -> None:
    files = {"src/content/brunchPage.json": COCO_MAYA_BRUNCH_JSON}
    locator = KeystaticJsonLocator(
        file_path="src/content/brunchPage.json",
        json_pointer=("singleton", "seo", "descriptionTemplate"),
    )
    current = resolve_current_value(files, locator)
    updated = apply_change(files, locator, current, "A fresh meta description for brunch.")
    assert (
        '"descriptionTemplate": "A fresh meta description for brunch."'
        in updated["src/content/brunchPage.json"]
    )
    assert (
        '"title": "Best Daily Brunch in Little Italy San Diego | Coco Maya"'
        in updated["src/content/brunchPage.json"]
    )


def test_resolves_louisiana_purchase_top_level_seo_title_no_wrapper() -> None:
    files = {"src/content/brunchPage/page.json": LOUISIANA_PURCHASE_BRUNCH_JSON}
    locator = KeystaticJsonLocator(
        file_path="src/content/brunchPage/page.json",
        json_pointer=("seo", "title"),
    )
    assert (
        resolve_current_value(files, locator)
        == "Weekend Creole Brunch in North Park | Louisiana Purchase"
    )


def test_applies_edit_to_louisiana_purchase_top_level_shape() -> None:
    files = {"src/content/brunchPage/page.json": LOUISIANA_PURCHASE_BRUNCH_JSON}
    locator = KeystaticJsonLocator(
        file_path="src/content/brunchPage/page.json",
        json_pointer=("seo", "title"),
    )
    current = resolve_current_value(files, locator)
    updated = apply_change(files, locator, current, "New North Park Brunch Title")
    assert '"title": "New North Park Brunch Title"' in updated["src/content/brunchPage/page.json"]
    assert '"href": "/menu"' in updated["src/content/brunchPage/page.json"]


def test_keystatic_json_pointer_not_found_requires_mapping() -> None:
    files = {"src/content/brunchPage.json": COCO_MAYA_BRUNCH_JSON}
    locator = KeystaticJsonLocator(
        file_path="src/content/brunchPage.json",
        json_pointer=("singleton", "seo", "missingField"),
    )
    with pytest.raises(SEOSiteMappingRequiredError):
        resolve_current_value(files, locator)


def test_keystatic_json_file_missing_requires_mapping() -> None:
    with pytest.raises(SEOSiteMappingRequiredError):
        resolve_current_value({}, KeystaticJsonLocator("missing.json", ("seo", "title")))


def test_resolves_and_edits_mdx_frontmatter_seo_title() -> None:
    files = {"src/content/blog/best-brunch.mdx": MDX_BLOG_POST}
    locator = FrontmatterLocator(file_path="src/content/blog/best-brunch.mdx", key="seoTitle")
    current = resolve_current_value(files, locator)
    assert current == "Best Brunch San Diego | Coco Maya"
    updated = apply_change(files, locator, current, "Updated Brunch Title | Coco Maya")
    updated_content = updated["src/content/blog/best-brunch.mdx"]
    assert 'seoTitle: "Updated Brunch Title | Coco Maya"' in updated_content
    assert 'title: "Best Brunch Spots in San Diego"' in updated_content
    assert "# Best Brunch Spots" in updated_content


def test_frontmatter_missing_block_requires_mapping() -> None:
    files = {"src/content/blog/no-frontmatter.mdx": "# No frontmatter here\n"}
    locator = FrontmatterLocator(file_path="src/content/blog/no-frontmatter.mdx", key="seoTitle")
    with pytest.raises(SEOSiteMappingRequiredError):
        resolve_current_value(files, locator)


def test_resolves_and_edits_astro_code_homepage_meta_title() -> None:
    files = {"src/lib/seo.ts": SEO_TS}
    locator = AstroCodeLocator(file_path="src/lib/seo.ts", binding_name="title")
    current = resolve_current_value(files, locator)
    assert current == "Wheyland Electric | Licensed Electrician"
    updated = apply_change(files, locator, current, "New Electrician Title")
    updated_content = updated["src/lib/seo.ts"]
    assert 'title: "New Electrician Title"' in updated_content
    assert 'description: "Licensed electrician serving North County San Diego."' in updated_content


def test_astro_code_ambiguous_binding_requires_mapping() -> None:
    files = {
        "src/lib/seo.ts": (
            'export const a = { title: "First" };\nexport const b = { title: "Second" };\n'
        )
    }
    locator = AstroCodeLocator(file_path="src/lib/seo.ts", binding_name="title")
    with pytest.raises(SEOSiteMappingRequiredError):
        resolve_current_value(files, locator)


def test_astro_code_missing_binding_requires_mapping() -> None:
    files = {"src/lib/seo.ts": "export const meta = {};\n"}
    locator = AstroCodeLocator(file_path="src/lib/seo.ts", binding_name="title")
    with pytest.raises(SEOSiteMappingRequiredError):
        resolve_current_value(files, locator)


def test_apply_change_refuses_when_file_drifted_since_approval() -> None:
    files = {"src/content/brunchPage.json": COCO_MAYA_BRUNCH_JSON}
    locator = KeystaticJsonLocator(
        file_path="src/content/brunchPage.json",
        json_pointer=("singleton", "seo", "title"),
    )
    with pytest.raises(SEOSiteMappingRequiredError, match="no longer matches"):
        apply_change(files, locator, "A stale approved value that is not in the file", "New")


def test_applies_edit_when_current_value_contains_non_ascii_characters() -> None:
    """json.dumps defaults to escaping non-ASCII as \\uXXXX, which never
    matches a file that stores the literal UTF-8 character (em dashes,
    curly quotes) -- this is the exact shape of coco-maya's real content."""
    files = {
        "src/content/brunchPage.json": (
            '{"singleton": {"seo": {"descriptionTemplate": '
            '"Best brunch — rooftop patio, craft cocktails, seven days a week."}}}'
        )
    }
    locator = KeystaticJsonLocator(
        file_path="src/content/brunchPage.json",
        json_pointer=("singleton", "seo", "descriptionTemplate"),
    )
    current = resolve_current_value(files, locator)
    updated = apply_change(files, locator, current, "A new description without an em dash.")
    assert (
        '"descriptionTemplate": "A new description without an em dash."'
        in updated["src/content/brunchPage.json"]
    )


def test_apply_change_refuses_ambiguous_duplicate_value() -> None:
    files = {"dup.json": '{"seo": {"title": "Same Value"}, "other": {"title": "Same Value"}}'}
    locator = KeystaticJsonLocator(file_path="dup.json", json_pointer=("seo", "title"))
    with pytest.raises(SEOSiteMappingRequiredError, match="occurs 2 times"):
        apply_change(files, locator, "Same Value", "New Value")


# ---------------------------------------------------------------------------
# Declarative page map
# ---------------------------------------------------------------------------

PAGE_MAP = {
    "/brunch": {
        "seo_title": {
            "source_type": "keystatic_json",
            "file_path": "src/content/brunchPage.json",
            "json_pointer": ["singleton", "seo", "title"],
        },
    },
    "/blog/{slug}": {
        "seo_title": {
            "source_type": "frontmatter",
            "file_path": "src/content/blog/{slug}.mdx",
            "key": "seoTitle",
        },
    },
    # Two templates that both match /menu/cocktails: a deliberately ambiguous map.
    "/menu/{page}": {
        "seo_title": {
            "source_type": "keystatic_json",
            "file_path": "src/content/menu.json",
            "json_pointer": ["seo", "title"],
        },
    },
    "/{section}/cocktails": {
        "seo_title": {
            "source_type": "keystatic_json",
            "file_path": "src/content/cocktails.json",
            "json_pointer": ["seo", "title"],
        },
    },
}
PREFIXES = ["src/content"]


def test_normalize_url_path_reduces_urls_to_their_path() -> None:
    assert normalize_url_path("https://example.com/brunch/") == "/brunch"
    assert normalize_url_path("https://example.com") == "/"
    assert normalize_url_path("/blog/post?utm=1#top") == "/blog/post"
    assert normalize_url_path("brunch") == "/brunch"


def test_page_map_resolves_exact_path_and_fills_blog_template() -> None:
    exact = resolve_entry(PAGE_MAP, "https://example.com/brunch/", PREFIXES)
    assert exact.url_path == "/brunch"
    locator = exact.fields[SiteChangeField.SEO_TITLE]
    assert isinstance(locator, KeystaticJsonLocator)
    assert locator.json_pointer == ("singleton", "seo", "title")

    post = resolve_entry(PAGE_MAP, "/blog/best-brunch-san-diego", PREFIXES)
    post_locator = post.fields[SiteChangeField.SEO_TITLE]
    assert isinstance(post_locator, FrontmatterLocator)
    assert post_locator.file_path == "src/content/blog/best-brunch-san-diego.mdx"
    assert post_locator.key == "seoTitle"


def test_ambiguous_page_map_blocks_only_that_page() -> None:
    with pytest.raises(SEOSiteMappingRequiredError, match="more than one"):
        resolve_entry(PAGE_MAP, "/menu/cocktails", PREFIXES)
    with pytest.raises(SEOSiteMappingRequiredError, match="no entry"):
        resolve_entry(PAGE_MAP, "/unmapped", PREFIXES)
    # Neighbouring pages in the same map are unaffected.
    assert resolve_entry(PAGE_MAP, "/brunch", PREFIXES).url_path == "/brunch"
    assert resolve_entry(PAGE_MAP, "/blog/another-post", PREFIXES).url_path == "/blog/another-post"


def test_page_map_refuses_files_outside_allowed_prefixes() -> None:
    with pytest.raises(SEOSiteMappingRequiredError, match="allowed site-change paths"):
        resolve_entry(PAGE_MAP, "/brunch", ["src/pages"])
    with pytest.raises(SEOSiteMappingRequiredError, match="allowed site-change paths"):
        resolve_entry(PAGE_MAP, "/brunch", [])
    escaping = {
        "/x": {
            "seo_title": {
                "source_type": "keystatic_json",
                "file_path": "src/content/../../secrets.json",
                "json_pointer": ["a"],
            }
        }
    }
    with pytest.raises(SEOSiteMappingRequiredError, match="allowed site-change paths"):
        resolve_entry(escaping, "/x", PREFIXES)


def test_page_map_rejects_unknown_fields_and_source_types() -> None:
    unknown_field = {
        "/x": {
            "favicon": {"source_type": "frontmatter", "file_path": "src/content/a.md", "key": "k"}
        }
    }
    with pytest.raises(SEOSiteMappingRequiredError, match="unknown field"):
        resolve_entry(unknown_field, "/x", PREFIXES)
    unknown_source = {
        "/x": {"seo_title": {"source_type": "wordpress", "file_path": "src/content/a.md"}}
    }
    with pytest.raises(SEOSiteMappingRequiredError, match="unsupported source_type"):
        resolve_entry(unknown_source, "/x", PREFIXES)


def test_page_map_is_read_from_the_publishing_contract_and_defaults_empty() -> None:
    assert page_map_from_contract({"page_map": PAGE_MAP}) == PAGE_MAP
    assert page_map_from_contract({}) == {}
    assert page_map_from_contract(None) == {}


def test_seeded_page_maps_resolve_within_their_allowed_prefixes() -> None:
    from scripts.seed_publishing_target_contracts import PAGE_MAPS, SITE_CHANGE_PREFIXES

    # Only real clients with a publishing target are mapped; Wheyland Electric is not a client.
    assert set(PAGE_MAPS) == {"LilosG/coco-maya", "LilosG/louisiana-purchase"}
    assert not any("wheyland" in repository.lower() for repository in PAGE_MAPS)
    for repository, page_map in PAGE_MAPS.items():
        prefixes = SITE_CHANGE_PREFIXES[repository]
        assert "/brunch" in page_map
        for url_path in page_map:
            sample = url_path.replace("{slug}", "a-post")
            entry = resolve_entry(page_map, sample, prefixes)
            assert entry.fields, (repository, url_path)
