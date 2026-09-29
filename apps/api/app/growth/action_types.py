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

# (product_key, action_type) -> the deterministic workflow key it dispatches
# directly. Every entry must exist in `execution.workflow_catalog.WORKFLOW_TYPES`
# and its handler must accept an empty `input_document` (self-contained runs).
DETERMINISTIC_ACTION_WORKFLOWS: dict[tuple[str, str], str] = {
    ("seo", "analysis"): "seo.analyze",
    ("seo", "analyze"): "seo.analyze",
    ("seo", "site_analysis"): "seo.analyze",
    ("gbp", "sync"): "gbp.sync",
    ("gbp", "profile_sync"): "gbp.sync",
    ("reviews", "ingest"): "reviews.ingest",
    ("reviews", "sync"): "reviews.ingest",
}


def deterministic_workflow_for(product_key: str, action_type: str) -> str | None:
    """Return the workflow key for deterministic Growth work, or ``None``.

    ``None`` means the action is reasoning/drafting work and must go through
    its product's governed Hermes agent.
    """
    return DETERMINISTIC_ACTION_WORKFLOWS.get((product_key, action_type))
