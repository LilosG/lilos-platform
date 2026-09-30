"""Record each client's Astro collection contract against its publishing target.

Contracts are keyed by ``repository_id`` because that is what identifies a client
site on a ``PublishingTarget``. Every entry below was read from that repository's
``src/content/config.ts``; none is inferred. A repository absent from this table
keeps an empty contract and is validated only against the universal floor of
title + description, which is safe but publishes less metadata.

Run after a target exists:

    uv run python -m scripts.seed_publishing_target_contracts

Idempotent: it only writes when the stored contract differs from the recorded one.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import select

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import PublishingTarget

# Standalone seed processes do not import the application model graph. Register the
# tables referenced by PublishingTarget's composite foreign key before SQLAlchemy
# sorts mapper dependencies during a flush. This mirrors the explicit model
# registration used by the other production seed entrypoints.
assert (
    PublishingTarget.metadata
    is IntegrationConnection.metadata
    is Provider.metadata
    is Location.metadata
    is Organization.metadata
)

# canonical name -> the key that client's schema declares.
# Verified against src/content/config.ts in each repository on 2026-08-27.
CONTRACTS: dict[str, dict[str, Any]] = {
    # Legacy `type: "content"` collections accept .md and .mdx. Collections built
    # on an Astro `glob()` loader accept only what the pattern matches, and a file
    # outside it is silently ignored rather than failing -- so file_extensions is
    # recorded from the loader pattern, not assumed.
    #
    # blog: title*, description*, date?, publishDate?, relatedServices[],
    # faqs[{question,answer}], serviceAreas[], image?, imageAlt?, draft(false)
    "LilosG/wheylandelectric-final-2.0": {
        "field_names": {
            "publish_date": "date",
            "related_services": "relatedServices",
            "service_areas": "serviceAreas",
            "image_alt": "imageAlt",
        },
        "required": ["title", "description"],
        "defaults": {"draft": False},
        "file_extensions": [".md", ".mdx"],
    },
    # blog: title*, description*, pubDate?, tags[], serviceAreas[z.enum],
    # services[z.enum], faqs[], canonical?, featured(false), draft(false)
    "LilosG/carlsbadfixit-final": {
        "field_names": {
            "publish_date": "pubDate",
            "related_services": "services",
            "service_areas": "serviceAreas",
            "image_alt": "imageAlt",
        },
        "required": ["title", "description"],
        "defaults": {"draft": False},
        "file_extensions": [".md", ".mdx"],
        # Copied from the repository's own `as const` arrays. A value outside
        # these is dropped rather than published, because z.enum rejects it.
        "enums": {
            "serviceAreas": [
                "carlsbad",
                "oceanside",
                "encinitas",
                "vista",
                "san-marcos",
                "bressi-ranch",
            ],
            "services": [
                "carpentry-woodwork",
                "electrical",
                "furniture-assembly-installation",
                "plumbing-fixtures-repairs",
                "honey-do-lists-small-repairs",
                "drywall-repair",
                "tv-mounting",
            ],
        },
    },
    # blog: title*, description*, publishDate* z.date(), category* z.enum,
    # relatedServices[], relatedCities[], tags[], faqs[{question,answer}]
    "LilosG/tamarackrestoration-final-2.0": {
        "field_names": {
            "publish_date": "publishDate",
            "related_services": "relatedServices",
            "image_alt": "imageAlt",
        },
        "required": ["title", "description", "publishDate", "category"],
        "date_format": "date",
        "defaults": {"draft": False, "category": "tips"},
        "file_extensions": [".md", ".mdx"],
        "enums": {
            "category": [
                "water-damage",
                "fire-damage",
                "mold",
                "flood",
                "insurance",
                "prevention",
                "leak-detection",
                "tips",
                "news",
            ]
        },
    },
    # blog: title*, description*, publishDate* z.string(), category* z.enum,
    # relatedServices[], serviceAreas[], tags[], ogImage?, faqs[]
    "LilosG/kelari-party-rentals-final": {
        "field_names": {
            "publish_date": "publishDate",
            "related_services": "relatedServices",
            "service_areas": "serviceAreas",
            "image_alt": "imageAlt",
        },
        "required": ["title", "description", "publishDate", "category"],
        "date_format": "string",
        # `category` is a required enum the model cannot know. The default keeps a
        # generated page buildable; selecting the most apt member per post needs the
        # allowed values passed into generation.
        "defaults": {"draft": False, "category": "Tips & Advice"},
        "file_extensions": [".md", ".mdx"],
        # Title case with spaces and an ampersand, exactly as declared. A
        # slug-style value such as "party-planning" is rejected by z.enum.
        "enums": {"category": ["Party Planning", "Rental Guide", "Local Guide", "Tips & Advice"]},
    },
    # blog: title*, description*, pubDate* z.coerce.date(), category?,
    # tags[], faqs[{question,answer}], serviceAreas[], image?, imageAlt?
    "LilosG/Postalsystems-final": {
        "field_names": {"publish_date": "pubDate", "image_alt": "imageAlt"},
        "required": ["title", "description", "pubDate"],
        "defaults": {"draft": False},
        "file_extensions": [".md", ".mdx"],
    },
    # blog loader: **/*.{md,mdx}
    # title*, description*, date* z.coerce.date(), category* z.string(),
    # faq[{question,answer}] -- singular key -- relatedServices?, serviceAreas?
    "LilosG/cococabana": {
        "field_names": {
            "publish_date": "date",
            "faqs": "faq",
            "related_services": "relatedServices",
            "service_areas": "serviceAreas",
        },
        "required": ["title", "description", "date", "category"],
        "defaults": {"category": "guides"},
        "file_extensions": [".md", ".mdx"],
    },
    # blog loader: **/*.mdx ONLY
    # title*, description*, date* z.coerce.date(), category* z.enum(BLOG_CATEGORIES),
    # faqs[{q,a}] -- q/a keys -- seoTitle?, image?, imageAlt?, tags?
    "LilosG/louisiana-purchase": {
        "field_names": {"publish_date": "date", "image_alt": "imageAlt"},
        "required": ["title", "description", "date", "category"],
        "faq_question_key": "q",
        "faq_answer_key": "a",
        "defaults": {"category": "Events"},
        "file_extensions": [".mdx"],
        "enums": {
            "category": [
                "Events",
                "Private Events",
                "North Park Guide",
                "Cocktails",
                "Brunch",
                "Dinner",
            ]
        },
    },
    # blog loader: **/*.{md,mdx}
    # title*, description*, publishDate* z.coerce.date(), category* z.enum,
    # relatedServices[max 3]?, tags[], draft(false)
    "LilosG/park101": {
        "field_names": {
            "publish_date": "publishDate",
            "related_services": "relatedServices",
            "image_alt": "imageAlt",
        },
        "required": ["title", "description", "publishDate", "category"],
        "defaults": {"draft": False, "category": "community"},
        "file_extensions": [".md", ".mdx"],
        "enums": {
            "category": [
                "game-day",
                "food-drink",
                "events",
                "weekly-specials",
                "venue",
                "community",
                "private-events",
            ]
        },
    },
    # blog loader: **/*.mdx ONLY
    # title*, metaTitle*, description*, category*, date* z.string(), image*, imageAlt*
    # Every one of those is non-optional, including image and imageAlt, which
    # generation does not yet produce -- publication fails fast with
    # CONTENT_FRONTMATTER_INCOMPLETE rather than breaking the build.
    "LilosG/miss-bs-coconut-club": {
        "field_names": {
            "publish_date": "date",
            "image_alt": "imageAlt",
            "seo_title": "metaTitle",
        },
        "required": [
            "title",
            "metaTitle",
            "description",
            "category",
            "date",
            "image",
            "imageAlt",
        ],
        "date_format": "string",
        "file_extensions": [".mdx"],
    },
    # blog loader: **/*.mdx ONLY
    # title*, seoTitle*, description*, date* z.coerce.date(), image*, imageAlt*
    "LilosG/coco-maya": {
        "field_names": {
            "publish_date": "date",
            "image_alt": "imageAlt",
            "seo_title": "seoTitle",
        },
        "required": ["title", "seoTitle", "description", "date", "image", "imageAlt"],
        "file_extensions": [".mdx"],
    },
    # blog loader: **/*.mdx ONLY
    # title*, description*, date* z.string(), image*, imageAlt?
    "LilosG/lobby-tiki-bar": {
        "field_names": {"publish_date": "date", "image_alt": "imageAlt"},
        "required": ["title", "description", "date", "image"],
        "date_format": "string",
        "file_extensions": [".mdx"],
    },
}


# --- Site-change page maps -------------------------------------------------
#
# Where each live page's SEO title and meta description actually live in the
# client repository, for the governed `seo.apply_site_change` executor. Every
# entry was read from the repository AND compared with the live page on
# 2026-09-30: a field is mapped only when the repository value equals the live
# <title>/<meta name="description"> exactly and carries no `{{token}}`
# placeholder (those are filled at render time, so the stored text is not what a
# visitor sees). A page or field absent here is refused as SITE_MAPPING_REQUIRED
# rather than guessed at.
#
# Wheyland Electric is deliberately absent: it is not a client.


def _keystatic_page(
    file_path: str,
    pointer: tuple[str, ...],
    *,
    description_key: str | None,
) -> dict[str, Any]:
    """One Keystatic JSON page: ``<pointer>.title`` and optionally its description."""
    fields: dict[str, Any] = {
        "seo_title": {
            "source_type": "keystatic_json",
            "file_path": file_path,
            "json_pointer": [*pointer, "title"],
        }
    }
    if description_key is not None:
        fields["meta_description"] = {
            "source_type": "keystatic_json",
            "file_path": file_path,
            "json_pointer": [*pointer, description_key],
        }
    return fields


def _blog_post_page(title_key: str, description_key: str) -> dict[str, Any]:
    return {
        "seo_title": {
            "source_type": "frontmatter",
            "file_path": "src/content/blog/{slug}.mdx",
            "key": title_key,
        },
        "meta_description": {
            "source_type": "frontmatter",
            "file_path": "src/content/blog/{slug}.mdx",
            "key": description_key,
        },
    }


# coco-maya: singleton-wrapped Keystatic files, `src/content/<name>.json`.
# url path -> (content file, meta description key or None when it is templated)
_COCO_MAYA_PAGES: dict[str, tuple[str, str | None]] = {
    "/": ("home", None),
    "/about": ("about", None),
    "/blog": ("blogIndexPage", "description"),
    "/brunch": ("brunchPage", "descriptionTemplate"),
    "/events": ("eventsPage", "descriptionTemplate"),
    "/faq": ("faqPage", "description"),
    "/happy-hour": ("happyHourPage", "description"),
    "/menu": ("menuPage", None),
    "/private-events": ("privateEventsIndexPage", None),
    "/private-events/inquire": ("eventInquiryPage", "description"),
    "/reservations": ("reservationsPage", None),
    "/the-space": ("spacePage", None),
}

# louisiana-purchase: top-level Keystatic files, `src/content/<name>/page.json`.
_LOUISIANA_PURCHASE_PAGES: dict[str, tuple[str, str | None]] = {
    "/brunch": ("brunchPage", "description"),
    "/happy-hour": ("happyHourPage", None),
    "/menu/cocktails": ("menuCocktailsPage", "description"),
    "/menu/dinner": ("menuDinnerPage", "description"),
    "/private-events": ("privateEventsIndexPage", None),
}

PAGE_MAPS: dict[str, dict[str, Any]] = {
    "LilosG/coco-maya": {
        **{
            url: _keystatic_page(
                f"src/content/{name}.json", ("singleton", "seo"), description_key=key
            )
            for url, (name, key) in _COCO_MAYA_PAGES.items()
        },
        # blog loader is **/*.mdx; `<title>` is seoTitle, the description is `description`.
        "/blog/{slug}": _blog_post_page("seoTitle", "description"),
    },
    "LilosG/louisiana-purchase": {
        **{
            url: _keystatic_page(f"src/content/{name}/page.json", ("seo",), description_key=key)
            for url, (name, key) in _LOUISIANA_PURCHASE_PAGES.items()
        },
        # every published post declares seoTitle; the page uses seoTitle || title.
        "/blog/{slug}": _blog_post_page("seoTitle", "description"),
    },
}

# Separate from each target's blog-only `allowed_path_prefix`.
SITE_CHANGE_PREFIXES: dict[str, list[str]] = {
    "LilosG/coco-maya": ["src/content"],
    "LilosG/louisiana-purchase": ["src/content"],
}


def full_contract(repository_id: str) -> dict[str, Any] | None:
    """The publishing contract plus this repository's page map, if it has either."""
    contract = CONTRACTS.get(repository_id)
    page_map = PAGE_MAPS.get(repository_id)
    if contract is None:
        return None
    return {**contract, "page_map": page_map} if page_map else contract


async def main() -> int:
    runtime = create_database_runtime(Settings())
    factory = runtime.require_session_factory()
    updated = 0
    skipped = 0
    async with factory() as session, session.begin():
        targets = list(await session.scalars(select(PublishingTarget)))
        for target in targets:
            contract = full_contract(target.repository_id)
            if contract is None:
                print(f"  no recorded contract for {target.repository_id} — left empty")
                skipped += 1
                continue
            prefixes = SITE_CHANGE_PREFIXES.get(target.repository_id, [])
            if (
                target.frontmatter_contract == contract
                and list(target.allowed_site_change_prefixes) == prefixes
            ):
                print(f"  unchanged: {target.repository_id}")
                continue
            target.frontmatter_contract = contract
            target.allowed_site_change_prefixes = prefixes
            print(f"  updated:   {target.repository_id}")
            updated += 1
    await runtime.dispose()
    print(
        json.dumps(
            {"targets": len(targets), "updated": updated, "without_contract": skipped},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
