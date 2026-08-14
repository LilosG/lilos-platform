# Packet 4A — SEO Crawl Engine

**Depends on:** Packet 1 (frozen contracts), Packet 3 (integration state)
**Owner:** Insights & Reporting specialist is NOT the owner. This is SEO product backend + minimal SEO page surface.
**Isolated worktree:** Yes
**Branch:** `packet/4a-seo-crawl-engine`
**Precedes:** Packet 4 (SC4-SEO cannot pass without this)

---

## Why this packet exists

`SC4-SEO-RECOMMENDATIONS` requires prioritized opportunities from real site data. That cannot pass, because LILOs does not currently have a crawler.

Evidence: `apps/api/app/products/seo/` contains no crawler module. The SEO page sends `seedPaths: ["/"]`, the service iterates the supplied seed list, no link discovery occurs against fetched documents, and the run reports `pages_crawled = len(targets)`. The interface presents a **Max pages** control on a backend that fetches exactly one URL and always will.

This is the reference case for the `AGENTS.md` "No UI without backend" rule. Verify the above against current `main` before writing code; if any part of it is now false, report that and adjust scope rather than rebuilding something that exists.

---

## Objective

Implement the controlled crawler required by Master Spec 13.43–13.46, executing through the existing `seo.crawl_or_analysis` workflow handler and durable worker runtime. Do not introduce a parallel execution path.

---

## In scope

### Crawl engine

- Breadth-first traversal from the site root, seeded from configured website + discovered sitemap URLs
- Same-host only. No external-domain traversal under any condition
- Link extraction from fetched HTML documents; this is the capability that does not currently exist
- Canonical URL normalization and deduplication; configurable query-parameter handling; exclusion patterns
- `robots.txt` fetched and respected; `nofollow` honored; identified user-agent
- Redirect chains followed to a bounded depth, destination recorded
- Controls that actually bind: `max_pages`, `max_depth`, crawl delay, per-request timeout, retry limit, total run timeout
- Politeness: bounded concurrency, delay between requests to the same host. The crawler must not create abusive load

### Persistence — per page

URL · HTTP status · content type · title · meta description · H1 · canonical · robots directives · internal links · external links · word count · structured-data presence · content hash · indexability · redirect destination · crawl depth

Persist incrementally as pages complete. A crawl that times out or errors must retain the pages already fetched and terminate in `partial`, not lose the run.

### Execution

- Runs through `seo.crawl_or_analysis` in the durable worker. A 250-page crawl must never execute inside an HTTP request
- Truthful progress: pages fetched, pages queued, current depth
- Terminal states `success | partial | error`, each with an operator-readable reason
- Idempotent re-runs; concurrent crawls of one website prevented or queued
- Tenant scope explicit at every query
- Cancellation supported

### Sitemap and robots

- Discover `robots.txt` and sitemap references; parse sitemap indexes
- Record listed URLs; compare sitemap inventory against crawl inventory
- Record robots availability and disallow rules relevant to the crawled host

### SEO page — minimum surface

Only what is needed to configure, observe, and read a crawl. Full SEO page convergence belongs to Packet 4.

- Crawl configuration whose limits match real backend limits — remove or bind any control that does not
- Running state with real progress, not an indefinite spinner
- Results: pages crawled, terminal state and reason, page inventory table with URL, status, depth, title presence, indexability
- Loading, empty, running, partial, failed, and success states, each with a recovery action
- No raw enum strings in client-facing text

---

## Explicitly out of scope

Opportunity detection · recommendation lifecycle · Search Console reporting UI · Insights redesign · broader SEO page convergence · visual system changes. Record anything found in these areas in the packet report; do not implement.

---

## Capacity finding — required

`max_pages` currently caps at 20. Determine from source whether that is an intentional product limit, a temporary safety limit, or an implementation limitation, and state which.

Then determine whether the architecture as built can safely support bounded crawls of approximately 100, 250, and 500 pages for a normal local-service site. If durable queueing, incremental persistence, politeness controls, or concurrency limits are required to reach those, implement what this packet's scope covers and state explicitly in the report what remains.

Do not silently let 20 become the permanent product limit because the UI now matches it.

---

## Acceptance scenarios

1. **SC4A-DISCOVERY:** A crawl of `wheylandelectric.com` discovers and persists more than one page through link extraction.
   - Evidence: crawl run ID, terminal state, and the actual `pages_crawled` count. State the number.

2. **SC4A-LIMITS:** `max_pages` binds. Runs at 25 and at 250 stop at the configured limit and record why.
   - Evidence: two run records with counts and stop reasons.

3. **SC4A-DEPTH:** `max_depth` binds and crawl depth is recorded per page.
   - Evidence: depth distribution from a completed run.

4. **SC4A-SAMEHOST:** No external-domain URL is fetched. External links are recorded, never traversed.
   - Evidence: test asserting refusal, plus absence of off-host URLs in a real run.

5. **SC4A-FIELDS:** Every field in the persistence list is populated for a fetched page, or explicitly null with a reason.
   - Evidence: one real page row, all fields shown.

6. **SC4A-DURABLE:** The crawl executes in the worker, not the request. The API returns promptly with a run reference while the crawl continues.
   - Evidence: API response time and the run progressing after the response returned.

7. **SC4A-PARTIAL:** A crawl interrupted by timeout or error retains fetched pages and terminates `partial` with a reason.
   - Evidence: test plus a real or induced case.

8. **SC4A-IDEMPOTENT:** Re-running a crawl does not duplicate page rows for the same URL in the same run scope.
   - Evidence: test.

9. **SC4A-TENANT:** Crawl runs and page inventory are tenant-scoped; cross-organization read fails.
   - Evidence: negative test.

10. **SC4A-ROBOTS:** `robots.txt` is fetched and disallow rules are respected.
    - Evidence: test with a fixture disallow rule.

11. **SC4A-SITEMAP:** Sitemap discovered and parsed; sitemap-vs-crawl comparison persisted.
    - Evidence: result from the real site, or a truthful statement that the site publishes no sitemap.

12. **SC4A-UI-TRUTH:** Every control on the crawl surface does what it says. No affordance implies unimplemented capability.
    - Evidence: list each control and what it actually triggers.

13. **SC4A-STATES:** Loading, empty, running, partial, failed, success each render with a recovery action.
    - Evidence: browser test or screenshots.

---

## Validation

Focused during iteration. At packet end:

```
npm run typecheck && npm run lint && npm run test && npm run build
uv run pytest tests/python/seo -v
uv run ruff check . && uv run mypy apps/api/app/products/seo
npm run check:browser
git diff --check
```

Integration tests requiring `LILOS_TEST_DATABASE_URL` must be run, not skipped. If the database is unavailable, say so and do not report COMPLETE.

---

## Constraints

- Use the existing workflow/worker/scheduler runtime. No parallel execution framework.
- No direct provider API calls outside registered connectors.
- No migration unless genuinely required; if required, expand-and-contract, with rollback documented.
- Do not modify files owned by other specialists per `docs/PLATFORM-OWNERSHIP-MAP.md`. If a shared contract must change, stop and report it.
- Do not merge. Do not push without explicit instruction.
- Crawl only `wheylandelectric.com` for live acceptance. No other client site.

---

## Report

Use the `AGENTS.md` packet report format, plus:

- The `pages_crawled` number from SC4A-DISCOVERY, stated plainly
- The `max_pages=20` capacity finding and its classification
- Every crawl-surface control and what it actually does
- Ledger row updates for the SEO capability, using the repository status vocabulary
- Adjacent work found and intentionally not implemented
