"""Fixed registry of product workflow types that may be started through the shared endpoint.

Every product-triggered workflow run must correspond to exactly one of these
keys. Product services validate a consumed workflow run's definition key
against the specific key they expect (see `ExecutionService.resolve_for_consumption`),
so a run started for one workflow type can never be substituted for another.
"""

WORKFLOW_TYPES: dict[str, tuple[str, str]] = {
    "content.publish": ("Publish governed content", "content"),
    "content.draft_revision": ("Generate AI-assisted content draft", "content"),
    "seo.crawl_or_analysis": ("Run SEO crawl execution", "seo"),
    "seo.analyze": ("Analyze SEO evidence and generate opportunities", "seo"),
    "gbp.generate_post": ("Generate AI-assisted Business Profile post", "gbp"),
    "gbp.publish_change": ("Publish an approved Business Profile change", "gbp"),
    "gbp.publish_post": ("Publish an approved Business Profile post", "gbp"),
    "gbp.upload_media": ("Upload an approved Business Profile media item", "gbp"),
    "reviews.publish_response": ("Publish an approved review response to the provider", "reviews"),
    "leads.send_communication": ("Send a planned lead communication", "leads"),
    "gbp.sync": ("Scheduled GBP profile discovery and sync", "gbp"),
    "reviews.ingest": ("Scheduled reviews ingestion", "reviews"),
}


def is_known_workflow_key(key: str) -> bool:
    return key in WORKFLOW_TYPES
