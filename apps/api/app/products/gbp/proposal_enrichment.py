"""Deterministic enrichment for approval-ready GBP post proposals.

Hermes may draft the post copy, but client-owned CTA and media selection are
server-owned product behavior. This service guarantees that automated GBP post
proposals are enriched before human approval rather than relying on optional
model arguments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.knowledge_service import BusinessKnowledgeService
from apps.api.app.config import Settings
from apps.api.app.integrations.google_drive_media import DriveImage, GoogleDriveMediaService
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot
from apps.api.app.products.gbp.post_generation_models import GBPPostAsset

_STOP_TERMS = {
    "about",
    "after",
    "again",
    "also",
    "been",
    "being",
    "business",
    "client",
    "company",
    "from",
    "have",
    "into",
    "local",
    "more",
    "north",
    "post",
    "service",
    "that",
    "their",
    "this",
    "through",
    "with",
    "your",
}
_SEASONAL_TERMS = {
    "christmas",
    "fall",
    "holiday",
    "holidays",
    "halloween",
    "newyear",
    "seasonal",
    "spring",
    "summer",
    "thanksgiving",
    "winter",
}


@dataclass(frozen=True, slots=True)
class GBPProposalEnrichment:
    call_to_action: dict[str, object] | None
    target_url: str | None
    asset: GBPPostAsset | None


class GBPPostProposalEnrichmentService:
    """Resolve a safe website CTA and client-scoped Drive image for a proposal."""

    def __init__(self) -> None:
        self.knowledge = BusinessKnowledgeService()
        self.drive = GoogleDriveMediaService()

    async def enrich(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        organization_id: UUID,
        location_id: UUID,
        gbp_location: GBPLocation,
        post_revision_id: UUID,
        content: str,
        requested_call_to_action: object,
    ) -> GBPProposalEnrichment:
        organization = await session.get(Organization, organization_id)
        if organization is None:
            raise LookupError("organization not found")

        snapshot = await session.scalar(
            select(GBPProfileSnapshot)
            .where(
                GBPProfileSnapshot.organization_id == organization_id,
                GBPProfileSnapshot.gbp_location_id == gbp_location.id,
            )
            .order_by(GBPProfileSnapshot.observed_at.desc())
            .limit(1)
        )
        profile = snapshot.normalized_profile if snapshot else {}
        knowledge = await self.knowledge.retrieve_for_content(
            session,
            organization_id=organization_id,
            location_id=location_id,
            content_title=content[:300] or "Google Business Profile update",
            audience="local prospective customers",
            intent="select the most relevant client-owned landing page for this GBP post",
            content_type="gbp_post",
            limit=10,
        )
        target_url = self._select_target_url(profile, knowledge, content)
        call_to_action = self._safe_call_to_action(requested_call_to_action, target_url)

        asset = await self._attach_best_drive_image(
            session,
            settings,
            organization_id=organization_id,
            organization_name=organization.name,
            post_revision_id=post_revision_id,
            content=content,
        )
        return GBPProposalEnrichment(
            call_to_action=call_to_action,
            target_url=target_url,
            asset=asset,
        )

    async def _attach_best_drive_image(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        organization_id: UUID,
        organization_name: str,
        post_revision_id: UUID,
        content: str,
    ) -> GBPPostAsset | None:
        existing = await session.scalar(
            select(GBPPostAsset).where(
                GBPPostAsset.organization_id == organization_id,
                GBPPostAsset.post_revision_id == post_revision_id,
            )
        )
        if existing is not None:
            return existing

        images = await self.drive.discover_images(settings, organization_name, limit=100)
        if not images:
            return None

        recent_assets = list(
            await session.scalars(
                select(GBPPostAsset)
                .where(
                    GBPPostAsset.organization_id == organization_id,
                    GBPPostAsset.source_type == "google_drive",
                )
                .order_by(GBPPostAsset.created_at.desc())
                .limit(12)
            )
        )
        recent_file_ids = {
            str((item.metadata_document or {}).get("file_id") or "") for item in recent_assets
        }
        unused = [image for image in images if image.file_id not in recent_file_ids]
        pool = unused or images
        selected = self._select_image(pool, content)
        if selected is None:
            return None

        proxy_url = self.drive.public_proxy_url(
            settings,
            organization_id=organization_id,
            image=selected,
        )
        if not proxy_url:
            return None

        folder = self._folder_bucket(selected.path)
        asset = GBPPostAsset(
            organization_id=organization_id,
            post_revision_id=post_revision_id,
            source_type="google_drive",
            source_reference=f"drive:{selected.file_id}",
            provider_fetch_url=proxy_url,
            metadata_document={
                "file_id": selected.file_id,
                "name": selected.name,
                "mime_type": selected.mime_type,
                "path": selected.path,
                "modified_time": selected.modified_time or "",
                "folder": folder,
                "selection": "topic_aware_non_repeating",
            },
            status="selected",
        )
        session.add(asset)
        await session.flush()
        return asset

    @classmethod
    def _select_image(cls, images: list[DriveImage], content: str) -> DriveImage | None:
        if not images:
            return None
        content_terms = cls._terms(content)
        seasonal = bool(content_terms & _SEASONAL_TERMS)
        preferred_folder = "seasonal" if seasonal else "work"

        preferred = [
            image for image in images if cls._folder_bucket(image.path) == preferred_folder
        ]
        if not preferred and preferred_folder != "general":
            preferred = [image for image in images if cls._folder_bucket(image.path) == "general"]
        pool = preferred or images

        def score(image: DriveImage) -> tuple[int, str, str]:
            searchable = cls._terms(f"{image.name} {image.path}")
            overlap = len(content_terms & searchable)
            folder_bonus = 100 if cls._folder_bucket(image.path) == preferred_folder else 0
            return (
                overlap * 50 + folder_bonus,
                image.modified_time or "",
                image.name.casefold(),
            )

        return max(pool, key=score)

    @classmethod
    def _select_target_url(
        cls,
        profile: dict[str, object],
        knowledge: dict[str, Any],
        content: str,
    ) -> str | None:
        content_terms = cls._terms(content)
        ranked: list[tuple[int, str]] = []
        pages = knowledge.get("website_knowledge")
        if isinstance(pages, list):
            for raw in pages:
                if not isinstance(raw, dict):
                    continue
                url = str(raw.get("url") or "").strip()
                if not cls._valid_http_url(url):
                    continue
                haystack = " ".join(
                    str(raw.get(key) or "") for key in ("url", "title", "h1", "body_text")
                )
                page_terms = cls._terms(haystack)
                score = len(content_terms & page_terms) * 10
                path = urlsplit(url).path.strip("/")
                if path:
                    score += 2
                if any(part in path.casefold() for part in ("service", "services")):
                    score += 2
                ranked.append((score, url))
        if ranked:
            ranked.sort(key=lambda item: (item[0], len(urlsplit(item[1]).path)), reverse=True)
            if ranked[0][0] > 0:
                return ranked[0][1]

        website = profile.get("websiteUri")
        if isinstance(website, str) and cls._valid_http_url(website.strip()):
            return website.strip()
        return ranked[0][1] if ranked else None

    @classmethod
    def _safe_call_to_action(
        cls, requested: object, target_url: str | None
    ) -> dict[str, object] | None:
        del cls, requested
        if target_url is None:
            return None
        return {"actionType": "LEARN_MORE", "url": target_url}

    @staticmethod
    def _folder_bucket(path: str) -> str | None:
        parts = {part.casefold() for part in path.replace("\\", "/").split("/") if part}
        for bucket in ("work", "general", "seasonal"):
            if bucket in parts:
                return bucket
        return None

    @staticmethod
    def _valid_http_url(value: str) -> bool:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _terms(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", value.casefold())
            if len(token) >= 4 and token not in _STOP_TERMS
        }
