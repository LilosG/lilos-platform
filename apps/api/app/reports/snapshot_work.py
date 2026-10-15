"""Work completed in the period, counted from existing records only.

Each group is something the platform has a record of finishing inside the period: a post Google
confirmed live, website content published, a review response published, an approved profile or
website change applied. Nothing here is inferred or invented.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.content.models import ContentItem, ContentPublication
from apps.api.app.products.gbp.models import GBPLocation, GBPPublication
from apps.api.app.products.gbp.operations_models import GBPPostPublication, GBPPostRevision
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision
from apps.api.app.products.reviews.service import REVIEW_REMOVED
from apps.api.app.reports.contracts import (
    ReportPeriod,
    ReportWorkGroup,
    ReportWorkSection,
    WorkKind,
)
from apps.api.app.reports.snapshot_reviews import RESPONSE_PUBLISHED, period_bounds

TITLE_LIMIT = 5
TITLE_LENGTH = 80
POST_VERIFIED = "verified"
CONTENT_PUBLISHED = "published"
SITE_CHANGE = "site_change"
SITE_CHANGE_LIVE = ("deployed", "verified")


def _short(text: str | None) -> str | None:
    line = " ".join((text or "").split())
    if not line:
        return None
    return line if len(line) <= TITLE_LENGTH else line[: TITLE_LENGTH - 1].rstrip() + "…"


def _titles(values: Sequence[str | None]) -> list[str]:
    seen: list[str] = []
    for value in values:
        short = _short(value)
        if short and short not in seen:
            seen.append(short)
    return seen[:TITLE_LIMIT]


async def build_work(
    session: AsyncSession,
    organization_id: UUID,
    period: ReportPeriod,
    location_ids: Sequence[UUID],
) -> ReportWorkSection:
    start, following = period_bounds(period)

    posts = (
        await session.execute(
            select(GBPPostRevision.content)
            .join(
                GBPPostPublication,
                and_(
                    GBPPostPublication.organization_id == GBPPostRevision.organization_id,
                    GBPPostPublication.post_revision_id == GBPPostRevision.id,
                ),
            )
            .join(
                GBPLocation,
                and_(
                    GBPLocation.organization_id == GBPPostRevision.organization_id,
                    GBPLocation.id == GBPPostRevision.gbp_location_id,
                ),
            )
            .where(
                GBPPostPublication.organization_id == organization_id,
                GBPPostPublication.status == POST_VERIFIED,
                GBPPostPublication.verified_at >= start,
                GBPPostPublication.verified_at < following,
                GBPLocation.location_id.in_(location_ids),
            )
            .order_by(GBPPostPublication.verified_at)
        )
    ).scalars()
    post_list = list(posts)

    content = list(
        (
            await session.execute(
                select(ContentItem.title)
                .where(
                    ContentItem.organization_id == organization_id,
                    ContentItem.status == CONTENT_PUBLISHED,
                    ContentItem.published_at >= start,
                    ContentItem.published_at < following,
                    ContentItem.location_id.is_(None) | ContentItem.location_id.in_(location_ids),
                )
                .order_by(ContentItem.published_at)
            )
        ).scalars()
    )

    responses = int(
        await session.scalar(
            select(func.count(ReviewResponseRevision.id))
            .join(
                Review,
                and_(
                    Review.organization_id == ReviewResponseRevision.organization_id,
                    Review.id == ReviewResponseRevision.review_id,
                ),
            )
            .where(
                ReviewResponseRevision.organization_id == organization_id,
                ReviewResponseRevision.status == RESPONSE_PUBLISHED,
                ReviewResponseRevision.published_at >= start,
                ReviewResponseRevision.published_at < following,
                Review.status != REVIEW_REMOVED,
                Review.location_id.in_(location_ids),
            )
        )
        or 0
    )

    profile_changes = int(
        await session.scalar(
            select(func.count(GBPPublication.id)).where(
                GBPPublication.organization_id == organization_id,
                GBPPublication.status == POST_VERIFIED,
                GBPPublication.verified_at >= start,
                GBPPublication.verified_at < following,
                GBPPublication.location_id.in_(location_ids),
            )
        )
        or 0
    )

    site_changes = list(
        (
            await session.execute(
                select(ContentPublication.target_path)
                .where(
                    ContentPublication.organization_id == organization_id,
                    ContentPublication.publication_kind == SITE_CHANGE,
                    ContentPublication.status.in_(SITE_CHANGE_LIVE),
                    ContentPublication.verified_at >= start,
                    ContentPublication.verified_at < following,
                )
                .order_by(ContentPublication.verified_at)
            )
        ).scalars()
    )

    return ReportWorkSection(
        groups=[
            ReportWorkGroup(
                kind=WorkKind.GBP_POST, count=len(post_list), titles=_titles(post_list)
            ),
            ReportWorkGroup(
                kind=WorkKind.WEBSITE_CONTENT, count=len(content), titles=_titles(content)
            ),
            ReportWorkGroup(kind=WorkKind.REVIEW_RESPONSE, count=responses, titles=[]),
            ReportWorkGroup(kind=WorkKind.GBP_PROFILE_CHANGE, count=profile_changes, titles=[]),
            ReportWorkGroup(
                kind=WorkKind.WEBSITE_CHANGE, count=len(site_changes), titles=_titles(site_changes)
            ),
        ]
    )
