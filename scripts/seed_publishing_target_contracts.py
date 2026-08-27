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
        # Left empty deliberately: the allowed members live in the repository's
        # serviceAreas/services arrays. Until they are copied here, values pass
        # through unchecked, so populate these before relying on those fields.
        "enums": {},
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
        "defaults": {"draft": False},
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
        "defaults": {"draft": False},
    },
    # blog: title*, description*, pubDate*, faqs*
    "LilosG/Postalsystems-final": {
        "field_names": {"publish_date": "pubDate", "image_alt": "imageAlt"},
        "required": ["title", "description", "pubDate"],
        "defaults": {"draft": False},
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
