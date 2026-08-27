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
from apps.api.app.products.content.models import PublishingTarget

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


async def main() -> int:
    runtime = create_database_runtime(Settings())
    factory = runtime.require_session_factory()
    updated = 0
    skipped = 0
    async with factory() as session, session.begin():
        targets = list(await session.scalars(select(PublishingTarget)))
        for target in targets:
            contract = CONTRACTS.get(target.repository_id)
            if contract is None:
                print(f"  no recorded contract for {target.repository_id} — left empty")
                skipped += 1
                continue
            if target.frontmatter_contract == contract:
                print(f"  unchanged: {target.repository_id}")
                continue
            target.frontmatter_contract = contract
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
