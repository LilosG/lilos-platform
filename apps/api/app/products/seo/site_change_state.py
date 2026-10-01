"""What an operator sees for an approved SEO change: where it is and why it stopped.

Derived from the publication the executor persisted -- never re-computed or guessed --
and expressed with typed codes and closed states so the UI switches on values instead
of reading prose. Missing evidence is `None`, never a default that looks like progress.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.content.models import ContentPublication, PublishingTarget
from apps.api.app.products.seo.models import SEORecommendationRevision
from apps.api.app.products.seo.site_change_codes import SiteChangeCode, blocked_code

# `publications.build_status` is "<gate>:<state>"; these are the states an operator sees.
_BUILD_STATE = {
    "success": "passed",
    "failed": "failed",
    "pending": "pending",
    "none": "unavailable",
}


def pull_request_url(repository_id: str | None, pull_request_id: str | None) -> str | None:
    if not repository_id or not pull_request_id:
        return None
    return f"https://github.com/{repository_id}/pull/{pull_request_id}"


def change_set_items(revision: Any) -> list[dict[str, object]]:
    """The approved edits, for a before/after display. Empty when there is no change set."""
    raw = revision.change_set
    items = raw.get("items") if isinstance(raw, dict) else None
    return (
        [dict(item) for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    )


def _build(publication: Any) -> tuple[str | None, str | None]:
    if publication is None:
        return None, None
    if publication.safe_error_code == SiteChangeCode.CHECKS_UNAVAILABLE:
        gate = (publication.build_status or "none:none").split(":", 1)[0]
        return gate, "unavailable"
    if not publication.build_status or ":" not in publication.build_status:
        return None, None
    gate, _, state = publication.build_status.partition(":")
    return gate, _BUILD_STATE.get(state)


def _verification(publication: Any) -> tuple[str | None, list[dict[str, object]]]:
    if publication is None:
        return None, []
    evidence = publication.verification_evidence or {}
    checks = [
        {key: check.get(key) for key in ("field", "expected", "observed", "state")}
        for check in evidence.get("checks", [])
        if isinstance(check, dict)
    ]
    if publication.verification_status:
        return str(publication.verification_status), checks
    return ("pending" if publication.status == "deployment_pending" else None), checks


def site_change_state(
    revision: Any, publication: Any | None, repository_id: str | None
) -> dict[str, object] | None:
    """The operator-facing state of one recommendation's site change, or None if it has none."""
    limitation = getattr(revision, "change_set_limitation_code", None)
    if revision.change_set is None and limitation is None:
        return None
    build_gate, build_state = _build(publication)
    verification_state, live_checks = _verification(publication)
    blocked = (
        blocked_code(publication.safe_error_code) if publication is not None else None
    ) or limitation
    return {
        **{
            key: getattr(publication, key, None)
            for key in (
                "workflow_run_id",
                "deployment_status",
                "approved_head_sha",
                "external_revision_id",
                "published_url",
                "verified_at",
            )
        },
        "publication_id": getattr(publication, "id", None),
        "mapping_state": (
            "required"
            if blocked == SiteChangeCode.SITE_MAPPING_REQUIRED
            else "mapped"
            if revision.change_set is not None
            else None
        ),
        "blocked_code": blocked,
        "publication_status": publication.status if publication is not None else None,
        "pull_request_url": (
            pull_request_url(repository_id, publication.external_pull_request_id)
            if publication is not None
            else None
        ),
        "build_gate": build_gate,
        "build_state": build_state,
        "verification_state": verification_state,
        "live_checks": live_checks,
    }


async def load_site_change_states(
    session: AsyncSession,
    organization_id: UUID,
    revisions: Sequence[SEORecommendationRevision],
) -> dict[UUID, dict[str, object]]:
    """Site-change state for every given revision that has one, in two tenant-scoped queries."""
    relevant = [
        revision
        for revision in revisions
        if revision.change_set is not None or revision.change_set_limitation_code is not None
    ]
    if not relevant:
        return {}
    publications = {
        publication.seo_recommendation_revision_id: publication
        for publication in await session.scalars(
            select(ContentPublication)
            .where(
                ContentPublication.organization_id == organization_id,
                ContentPublication.publication_kind == "site_change",
                ContentPublication.seo_recommendation_revision_id.in_(
                    [revision.id for revision in relevant]
                ),
            )
            .order_by(ContentPublication.created_at)  # latest wins below
        )
    }
    repositories = {
        target.id: target.repository_id
        for target in await session.scalars(
            select(PublishingTarget).where(
                PublishingTarget.organization_id == organization_id,
                PublishingTarget.id.in_(
                    {publication.publishing_target_id for publication in publications.values()}
                ),
            )
        )
    }
    states: dict[UUID, dict[str, object]] = {}
    for revision in relevant:
        publication = publications.get(revision.id)
        state = site_change_state(
            revision,
            publication,
            repositories.get(publication.publishing_target_id) if publication else None,
        )
        if state is not None:
            states[revision.id] = state
    return states
