# Phase 13 Acceptance

Migration `20260803_0010` establishes confirmed website/property scope, deterministic URL identities, bounded crawl intent, quality-labelled Search Console observations, evidence-backed opportunities, immutable recommendation revisions, separate implementation tasks, verification evidence, and fixed-window outcomes. Missing data is distinct from zero; scoring is deterministic and explainable; AI is optional.

The prior "Phase 13 status: complete" claim covered only the domain model and
a handful of pure deterministic functions (URL normalization, crawl-target
validation, scoring, missing-data wrapping) — there was no service layer, no
API routes, and no frontend. This pass built the entire application surface
from that foundation. A new `SEOService` reuses the existing pure functions
and adds: website confirmation, Search Console property mapping (gated on a
real connected `IntegrationConnection`, the same pattern as Content's
publishing targets), a real bounded same-host crawler (`httpx`, strict
timeout, small page cap, SSRF-safe host allowlisting via the existing
`validate_crawl_target`) that extracts technical/on-page signals (title,
meta description, canonical link, H1 count, HTTP status) and deterministically
generates deduplicated opportunities via the existing `opportunity_score`,
local landing-page gap detection (confirmed locations without a matching
crawled page), a recommendation approval workflow, implementation-task
tracking with verification evidence, and outcome recording with baseline and
measurement windows. Every mutating action writes a real audit event via the
shared `AuditEventService`/`AuditEventRepository`; opportunity identification
and recommendations awaiting approval raise real notifications via the
shared `NotificationService`. Tenant-scoped read routes were added for
websites, search properties, opportunities, recommendations, implementation
tasks, landing-page gaps, summary, and audit history — all reusing existing
shared services for authentication, authorization, entitlements, and audit,
with no duplicate product-specific infrastructure. A typed `errors.py`
replaces bare exceptions. The crawler's HTTP client is injectable
(`http_client_factory`), so integration tests exercise the real code path
against a deterministic `httpx.MockTransport` rather than the network. A
real protected `/seo` frontend route renders truthful readiness, website
confirmation, Search Console status, landing-page gaps, a crawl trigger, an
opportunity queue, and recommendation/implementation/verification controls —
no fixture data, no dead buttons. 9 new backend integration tests plus a new
Playwright case were added; full repository validation was run.

Live Search Console query/page metric sync remains genuinely blocked on real
Search Console OAuth credentials, which were not configured or requested
this pass — crawling and technical/on-page analysis require no such
credentials and are fully real. Existing Starlette/httpx warning remains
unchanged. Phase 13 status: complete for all work not blocked on Search
Console OAuth credentials.
