"""Normalize product-owned proposal and execution state for Growth reconciliation.

Growth never becomes the source of truth for product approval, publication, or
verification. This adapter reads the canonical product records referenced by an
agent run and projects them into a small cross-product lifecycle contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentPublication,
    ContentRevision,
)
from apps.api.app.products.gbp.operations_models import (
    GBPChangeSet,
    GBPPostPublication,
    GBPPostRevision,
)
from apps.api.app.products.reviews.models import ReviewResponseRevision
from apps.api.app.products.seo.models import (
    SEOCrawlRun,
    SEOImplementationTask,
    SEORecommendationRevision,
)

ArtifactState = Literal["pending", "succeeded", "rejected", "failed"]


@dataclass(frozen=True, slots=True)
class GrowthArtifactState:
    state: ArtifactState
    product_status: str
    safe_code: str | None = None


class GrowthArtifactLifecycleService:
    """Read canonical product state without duplicating product lifecycle rules."""

    async def resolve(
        self,
        session: AsyncSession,
        organization_id: UUID,
        reference: str,
    ) -> GrowthArtifactState:
        kind, separator, raw_id = reference.partition(":")
        if not separator:
            return GrowthArtifactState("pending", "unresolved", "ARTIFACT_REFERENCE_INVALID")
        try:
            artifact_id = UUID(raw_id)
        except ValueError:
            return GrowthArtifactState("pending", "unresolved", "ARTIFACT_REFERENCE_INVALID")

        if kind == "gbp-change-set":
            return await self._gbp_change_set(session, organization_id, artifact_id)
        if kind == "gbp-post-revision":
            return await self._gbp_post(session, organization_id, artifact_id)
        if kind == "review-response-revision":
            return await self._review_response(session, organization_id, artifact_id)
        if kind == "content-item":
            return await self._content_item(session, organization_id, artifact_id)
        if kind == "content-brief":
            return await self._content_brief(session, organization_id, artifact_id)
        if kind == "content-revision":
            return await self._content_revision(session, organization_id, artifact_id)
        if kind == "seo-recommendation":
            return await self._seo_recommendation(session, organization_id, artifact_id)
        if kind == "seo-crawl-run":
            return await self._seo_crawl(session, organization_id, artifact_id)
        return GrowthArtifactState("pending", "unsupported", "ARTIFACT_REFERENCE_UNSUPPORTED")

    async def _gbp_change_set(
        self, session: AsyncSession, organization_id: UUID, artifact_id: UUID
    ) -> GrowthArtifactState:
        item = await session.scalar(
            select(GBPChangeSet).where(
                GBPChangeSet.organization_id == organization_id,
                GBPChangeSet.id == artifact_id,
            )
        )
        if item is None:
            return GrowthArtifactState("failed", "missing", "DOWNSTREAM_ARTIFACT_MISSING")
        if item.status == "verified":
            return GrowthArtifactState("succeeded", item.status)
        if item.status == "rejected":
            return GrowthArtifactState("rejected", item.status, "DOWNSTREAM_PROPOSAL_REJECTED")
        if item.status == "failed":
            return GrowthArtifactState("failed", item.status, "DOWNSTREAM_EXECUTION_FAILED")
        code = "DOWNSTREAM_RECONCILIATION_REQUIRED" if item.status == "reconciliation_required" else None
        return GrowthArtifactState("pending", item.status, code)

    async def _gbp_post(
        self, session: AsyncSession, organization_id: UUID, artifact_id: UUID
    ) -> GrowthArtifactState:
        revision = await session.scalar(
            select(GBPPostRevision).where(
                GBPPostRevision.organization_id == organization_id,
                GBPPostRevision.id == artifact_id,
            )
        )
        if revision is None:
            return GrowthArtifactState("failed", "missing", "DOWNSTREAM_ARTIFACT_MISSING")
        if revision.status in {"rejected", "superseded"}:
            return GrowthArtifactState("rejected", revision.status, "DOWNSTREAM_PROPOSAL_REJECTED")
        publication = await session.scalar(
            select(GBPPostPublication)
            .where(
                GBPPostPublication.organization_id == organization_id,
                GBPPostPublication.post_revision_id == revision.id,
            )
            .order_by(GBPPostPublication.created_at.desc())
            .limit(1)
        )
        if publication is None:
            return GrowthArtifactState("pending", revision.status)
        if publication.status == "verified":
            return GrowthArtifactState("succeeded", publication.status)
        if publication.status in {"failed", "cancelled", "expired"}:
            return GrowthArtifactState(
                "failed",
                publication.status,
                publication.safe_error_code or "DOWNSTREAM_EXECUTION_FAILED",
            )
        code = (
            "DOWNSTREAM_RECONCILIATION_REQUIRED"
            if publication.status == "reconciliation_required"
            else None
        )
        return GrowthArtifactState("pending", publication.status, code)

    async def _review_response(
        self, session: AsyncSession, organization_id: UUID, artifact_id: UUID
    ) -> GrowthArtifactState:
        revision = await session.scalar(
            select(ReviewResponseRevision).where(
                ReviewResponseRevision.organization_id == organization_id,
                ReviewResponseRevision.id == artifact_id,
            )
        )
        if revision is None:
            return GrowthArtifactState("failed", "missing", "DOWNSTREAM_ARTIFACT_MISSING")
        if revision.status == "published":
            return GrowthArtifactState("succeeded", revision.status)
        if revision.status in {"rejected", "superseded"}:
            return GrowthArtifactState("rejected", revision.status, "DOWNSTREAM_PROPOSAL_REJECTED")
        if revision.status == "failed":
            return GrowthArtifactState(
                "failed",
                revision.status,
                revision.safe_error_code or "DOWNSTREAM_EXECUTION_FAILED",
            )
        code = (
            "DOWNSTREAM_RECONCILIATION_REQUIRED"
            if revision.status == "reconciliation_required"
            else None
        )
        return GrowthArtifactState("pending", revision.status, code)

    async def _content_item(
        self, session: AsyncSession, organization_id: UUID, artifact_id: UUID
    ) -> GrowthArtifactState:
        item = await session.scalar(
            select(ContentItem).where(
                ContentItem.organization_id == organization_id,
                ContentItem.id == artifact_id,
            )
        )
        if item is None:
            return GrowthArtifactState("failed", "missing", "DOWNSTREAM_ARTIFACT_MISSING")
        if item.status == "published":
            return GrowthArtifactState("succeeded", item.status)
        if item.status in {"failed", "archived"}:
            return GrowthArtifactState("failed", item.status, "DOWNSTREAM_EXECUTION_FAILED")
        code = "DOWNSTREAM_RECONCILIATION_REQUIRED" if item.status == "reconciliation_required" else None
        return GrowthArtifactState("pending", item.status, code)

    async def _content_brief(
        self, session: AsyncSession, organization_id: UUID, artifact_id: UUID
    ) -> GrowthArtifactState:
        brief = await session.scalar(
            select(ContentBrief).where(
                ContentBrief.organization_id == organization_id,
                ContentBrief.id == artifact_id,
            )
        )
        if brief is None:
            return GrowthArtifactState("failed", "missing", "DOWNSTREAM_ARTIFACT_MISSING")
        if brief.status == "ready":
            return GrowthArtifactState("succeeded", brief.status)
        if brief.status in {"rejected", "failed", "superseded"}:
            return GrowthArtifactState("failed", brief.status, "DOWNSTREAM_EXECUTION_FAILED")
        return GrowthArtifactState("pending", brief.status)

    async def _content_revision(
        self, session: AsyncSession, organization_id: UUID, artifact_id: UUID
    ) -> GrowthArtifactState:
        revision = await session.scalar(
            select(ContentRevision).where(
                ContentRevision.organization_id == organization_id,
                ContentRevision.id == artifact_id,
            )
        )
        if revision is None:
            return GrowthArtifactState("failed", "missing", "DOWNSTREAM_ARTIFACT_MISSING")
        if revision.status in {"rejected", "superseded"}:
            return GrowthArtifactState("rejected", revision.status, "DOWNSTREAM_PROPOSAL_REJECTED")
        publication = await session.scalar(
            select(ContentPublication)
            .where(
                ContentPublication.organization_id == organization_id,
                ContentPublication.content_revision_id == revision.id,
            )
            .order_by(ContentPublication.created_at.desc())
            .limit(1)
        )
        if publication is None:
            return GrowthArtifactState("pending", revision.status)
        if publication.status == "verified":
            return GrowthArtifactState("succeeded", publication.status)
        if publication.status in {"failed", "rolled_back"}:
            return GrowthArtifactState(
                "failed",
                publication.status,
                publication.safe_error_code or "DOWNSTREAM_EXECUTION_FAILED",
            )
        code = (
            "DOWNSTREAM_RECONCILIATION_REQUIRED"
            if publication.status == "reconciliation_required"
            else None
        )
        return GrowthArtifactState("pending", publication.status, code)

    async def _seo_recommendation(
        self, session: AsyncSession, organization_id: UUID, artifact_id: UUID
    ) -> GrowthArtifactState:
        revision = await session.scalar(
            select(SEORecommendationRevision).where(
                SEORecommendationRevision.organization_id == organization_id,
                SEORecommendationRevision.id == artifact_id,
            )
        )
        if revision is None:
            return GrowthArtifactState("failed", "missing", "DOWNSTREAM_ARTIFACT_MISSING")
        if revision.status == "rejected":
            return GrowthArtifactState("rejected", revision.status, "DOWNSTREAM_PROPOSAL_REJECTED")
        task = await session.scalar(
            select(SEOImplementationTask)
            .where(
                SEOImplementationTask.organization_id == organization_id,
                SEOImplementationTask.recommendation_revision_id == revision.id,
            )
            .order_by(SEOImplementationTask.created_at.desc())
            .limit(1)
        )
        if task is None:
            return GrowthArtifactState("pending", revision.status)
        if task.status == "verified" or task.verified_at is not None:
            return GrowthArtifactState("succeeded", "verified")
        if task.status in {"failed", "cancelled"}:
            return GrowthArtifactState("failed", task.status, "DOWNSTREAM_EXECUTION_FAILED")
        return GrowthArtifactState("pending", task.status)

    async def _seo_crawl(
        self, session: AsyncSession, organization_id: UUID, artifact_id: UUID
    ) -> GrowthArtifactState:
        crawl = await session.scalar(
            select(SEOCrawlRun).where(
                SEOCrawlRun.organization_id == organization_id,
                SEOCrawlRun.id == artifact_id,
            )
        )
        if crawl is None:
            return GrowthArtifactState("failed", "missing", "DOWNSTREAM_ARTIFACT_MISSING")
        if crawl.status in {"completed", "complete", "succeeded", "success"}:
            return GrowthArtifactState("succeeded", crawl.status)
        if crawl.status in {"error", "failed", "cancelled"}:
            return GrowthArtifactState("failed", crawl.status, "DOWNSTREAM_EXECUTION_FAILED")
        return GrowthArtifactState("pending", crawl.status)
