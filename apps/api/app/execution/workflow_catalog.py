"""Fixed registry of product workflow types that may be started through the shared endpoint.

Every product-triggered workflow run must correspond to exactly one of these
keys. Product services validate a consumed workflow run's definition key
against the specific key they expect (see `ExecutionService.resolve_for_consumption`),
so a run started for one workflow type can never be substituted for another.
"""

WORKFLOW_TYPES: dict[str, tuple[str, str]] = {
    "content.publish": ("Publish governed content", "content"),
    "seo.crawl_or_analysis": ("Run SEO crawl or analysis execution", "seo"),
    "gbp.publish_change": ("Publish an approved Business Profile change", "gbp"),
    "gbp.publish_post": ("Publish an approved Business Profile post", "gbp"),
    "reviews.publish_response": ("Publish an approved review response to the provider", "reviews"),
}


def is_known_workflow_key(key: str) -> bool:
    return key in WORKFLOW_TYPES
