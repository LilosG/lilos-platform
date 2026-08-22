# Operational orchestration

This document records the product behavior implemented by the operations-completion branch.

- Google Business Profile discovery uses confirmed platform-location mappings and reports per-location sync freshness from `GBPLocation.last_synced_at`.
- Operator-run workflows enqueue durable jobs explicitly; product reservation workflows remain non-enqueued until their product mutation reserves the run.
- The Automations workspace supports run-now execution, recurring schedule creation, cadence updates, pause/resume, overdue detection, and failure detail for independently executable workflows.
- A single authorized GitHub repository is reconciled to the organization's default Astro publishing target at `src/content/blog`; multi-repository installations remain explicit.
- SEO analysis combines persisted crawl issues, Search Console evidence, and Google PageSpeed Insights into scored SEO opportunities, recommendation revisions, and Content opportunities.
- `gbp.generate_post` creates an approval-required, grounded GBP post draft from approved business facts, GBP/website knowledge, and recent-post history. When the organization's shared Google Drive folder can be identified safely, it selects a client-scoped image and stores a signed provider-media reference for publication.
- Approved GBP posts publish through the existing provider workflow and include the selected Drive image when available.

DataForSEO credentials are optional enrichment inputs; the deterministic crawl/GSC/PageSpeed opportunity layer does not depend on them.
