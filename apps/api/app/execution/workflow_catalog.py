"""Fixed registry of product workflow types that may be started through the shared endpoint.

Every product-triggered workflow run must correspond to exactly one of these
keys. Product services validate a consumed workflow run's definition key
against the specific key they expect (see `ExecutionService.resolve_for_consumption`),
so a run started for one workflow type can never be substituted for another.
"""

WORKFLOW_TYPES: dict[str, tuple[str, str]] = {
    "content.publish": ("Publish governed content", "content"),
    "content.draft_revision": ("Generate AI-assisted content draft", "content"),
    "content.compose": ("Write content from a plain prompt", "content"),
    "seo.crawl_or_analysis": ("Run SEO crawl execution", "seo"),
    "seo.analyze": ("Analyze SEO evidence and generate opportunities", "seo"),
    "seo.sync_search_console": ("Sync Search Console observations", "seo"),
    "insights.sync_analytics": ("Sync GA4 metrics", "insights"),
    "seo.apply_site_change": ("Apply an approved SEO change set to the client site", "seo"),
    "gbp.generate_post": ("Generate AI-assisted Business Profile post", "gbp"),
    "gbp.publish_change": ("Publish an approved Business Profile change", "gbp"),
    "gbp.publish_post": ("Publish an approved Business Profile post", "gbp"),
    "gbp.upload_media": ("Upload an approved Business Profile media item", "gbp"),
    "gbp.publish_special_hours": ("Publish approved Business Profile special hours", "gbp"),
    "reviews.publish_response": ("Publish an approved review response to the provider", "reviews"),
    "leads.send_communication": ("Send a planned lead communication", "leads"),
    "gbp.sync": ("Scheduled GBP profile discovery and sync", "gbp"),
    "gbp.sync_performance": ("Scheduled GBP performance metrics sync", "gbp"),
    "reviews.ingest": ("Scheduled reviews ingestion", "reviews"),
    "organization.remove": ("Permanently remove an archived client's data", "platform"),
    "agent.gbp": ("Hermes GBP governed agent", "gbp"),
    "agent.seo": ("Hermes SEO evidence agent", "seo"),
    "agent.content": ("Hermes grounded Content agent", "content"),
    "agent.reviews": ("Hermes governed Reviews agent", "reviews"),
    "agent.leads": ("Hermes governed Leads agent", "leads"),
    "agent.insights": ("Hermes cross-product Insights agent", "insights"),
    "agent.growth": ("Hermes cross-product Growth planner", "growth"),
}


# Workflows only the platform may start. A tenant-facing route must treat these as unknown:
# they act on the organization itself, not on one of its products.
PLATFORM_ONLY_WORKFLOWS = frozenset({"organization.remove"})


def is_tenant_workflow_key(key: str) -> bool:
    """A known workflow a client organization's own users may list, start or schedule."""
    return key in WORKFLOW_TYPES and key not in PLATFORM_ONLY_WORKFLOWS


def is_known_workflow_key(key: str) -> bool:
    return key in WORKFLOW_TYPES
