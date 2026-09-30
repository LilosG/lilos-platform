"""Classify Growth actions as deterministic work or Hermes reasoning work.

Deterministic work (crawls, syncs, scoring, verification, measurement) is
code, never an LLM call (CLAUDE.md architecture principle 1). Before this
module existed, `GrowthService.dispatch_ready` routed every `workflow`-mode
action through a Hermes agent, including ones whose product_key/action_type
pair names a plain scheduled sync or analysis pass with no reasoning in it.
Two such actions in the same (organization, location, skill) scope then
collided on the single active Hermes scoped session (`HERMES_SCOPED_SESSION_BUSY`),
and their sibling died to a handful of retries with second-scale backoff
while the winning Hermes run took minutes.

Only self-contained deterministic workflows are classified here: ones whose
handler needs nothing beyond `(organization_id, location_id)`, matching the
registrations in `execution.workflow_catalog.WORKFLOW_TYPES`. Workflows that
need extra identifiers the Growth action model does not yet carry (a crawl's
target website, for instance) are left as agent-routed until Milestone 2
extends the action model — see the Milestone 1 PR description.
"""

from __future__ import annotations

from enum import StrEnum


class GrowthActionType(StrEnum):
    """The closed vocabulary of Growth action types LILOs acts on.

    Hermes may still name other, purely descriptive action types (they route by
    their product and never match here). What this enum closes is every type the
    platform makes a *decision* on, so no decision rests on matching English:

    - deterministic work dispatched straight to a workflow, and
    - governed site changes: work on a client's live site (page metadata, headings,
      schema, links, crawl-detected technical issues) that belongs to the SEO
      product's approved-change-set path and must never be published as Content.

    `SiteChangeField` values and the crawl issue codes are mirrored here by value;
    tests assert the parity so the sets cannot drift apart.
    """

    # Deterministic, self-contained workflows.
    ANALYSIS = "analysis"
    ANALYZE = "analyze"
    SITE_ANALYSIS = "site_analysis"
    SYNC = "sync"
    PROFILE_SYNC = "profile_sync"
    INGEST = "ingest"

    # Governed site changes: the umbrella type plus one per `SiteChangeField`.
    SITE_IMPLEMENTATION = "site_implementation"
    SEO_TITLE = "seo_title"
    META_DESCRIPTION = "meta_description"
    H1 = "h1"
    BODY_SECTION = "body_section"
    SCHEMA = "schema"
    INTERNAL_LINK = "internal_link"

    # Governed site changes detected by the crawl (`CRAWL_VERIFIABLE_ISSUES`).
    MISSING_TITLE = "missing_title"
    MISSING_META_DESCRIPTION = "missing_meta_description"
    MISSING_H1 = "missing_h1"
    MULTIPLE_H1 = "multiple_h1"
    NON_200_STATUS = "non_200_status"
    TITLE_TRUNCATED = "title_truncated"
    META_DESCRIPTION_TRUNCATED = "meta_description_truncated"
    H1_TRUNCATED = "h1_truncated"


SITE_CHANGE_ACTION_TYPES: frozenset[GrowthActionType] = frozenset(
    {
        GrowthActionType.SITE_IMPLEMENTATION,
        GrowthActionType.SEO_TITLE,
        GrowthActionType.META_DESCRIPTION,
        GrowthActionType.H1,
        GrowthActionType.BODY_SECTION,
        GrowthActionType.SCHEMA,
        GrowthActionType.INTERNAL_LINK,
        GrowthActionType.MISSING_TITLE,
        GrowthActionType.MISSING_META_DESCRIPTION,
        GrowthActionType.MISSING_H1,
        GrowthActionType.MULTIPLE_H1,
        GrowthActionType.NON_200_STATUS,
        GrowthActionType.TITLE_TRUNCATED,
        GrowthActionType.META_DESCRIPTION_TRUNCATED,
        GrowthActionType.H1_TRUNCATED,
    }
)


def is_site_change_action(action_type: str | None) -> bool:
    """True only when ``action_type`` is exactly a governed site-change type.

    An exact enum lookup, never a substring match: prose, titles and hypotheses
    play no part in deciding where work is routed.
    """
    if action_type is None:
        return False
    try:
        return GrowthActionType(action_type) in SITE_CHANGE_ACTION_TYPES
    except ValueError:
        return False


# (product_key, action_type) -> the deterministic workflow key it dispatches
# directly. Every entry must exist in `execution.workflow_catalog.WORKFLOW_TYPES`
# and its handler must accept an empty `input_document` (self-contained runs).
DETERMINISTIC_ACTION_WORKFLOWS: dict[tuple[str, GrowthActionType], str] = {
    ("seo", GrowthActionType.ANALYSIS): "seo.analyze",
    ("seo", GrowthActionType.ANALYZE): "seo.analyze",
    ("seo", GrowthActionType.SITE_ANALYSIS): "seo.analyze",
    ("gbp", GrowthActionType.SYNC): "gbp.sync",
    ("gbp", GrowthActionType.PROFILE_SYNC): "gbp.sync",
    ("reviews", GrowthActionType.INGEST): "reviews.ingest",
    ("reviews", GrowthActionType.SYNC): "reviews.ingest",
}


def deterministic_workflow_for(product_key: str, action_type: str) -> str | None:
    """Return the workflow key for deterministic Growth work, or ``None``.

    ``None`` means the action is reasoning/drafting work and must go through
    its product's governed Hermes agent.
    """
    try:
        typed = GrowthActionType(action_type)
    except ValueError:
        return None
    return DETERMINISTIC_ACTION_WORKFLOWS.get((product_key, typed))
