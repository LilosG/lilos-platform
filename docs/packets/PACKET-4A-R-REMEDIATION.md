# Packet 4A-R — SEO Crawl Engine Remediation

**Branch:** `packet/4a-seo-crawl-engine` (continue on the existing branch, on top of `79c64a8`)
**Builder:** DeepSeek V4 Pro
**Source:** release-auditor findings against Packet 4A, verdict REJECT (7 of 13 scenarios failed)
**Packet:** `docs/packets/PACKET-4A-SEO-CRAWL-ENGINE.md`

The audit was correct. Two findings are regressions introduced by the original 4A run and are the priority.

**Editing constraint: targeted edits only. Do not `Write` whole existing files.** The 4A run rewrote `service.py` wholesale and silently deleted two things; that is why this packet exists.

---

## A. Regressions — fix first

### A1. Opportunity creation was deleted

The previous `run_crawl()` created `SEOOpportunity` records per technical issue per page. The new `execute_crawl()` creates none. Recover the original with:

```
git show 8678399:apps/api/app/products/seo/service.py | sed -n '478,515p'
```

Restore that behavior inside the new crawl path, preserving exactly:

- one opportunity per entry in the page's `technical_issues`
- `deduplication_key` as `f"{digest}.{issue}"` using the same digest basis as before
- the existing-active check (`organization_id` + `deduplication_key` + `active_marker == "active"`) before insert
- `evidence={"url": ..., "issue": ...}`, `source_versions=["crawl.v1"]`, `score_version=1`, `status="identified"`, `version=1`
- `opportunity_score()` called with the same arguments as before

**Do not improve the scoring.** The original passes fixed inputs (`search_potential=40, business_value=40, relevance=60, confidence=90, urgency=30, effort=10`) for every opportunity, so a missing title and a non-200 status receive identical priority. That is a known limitation, not a bug to fix here — real prioritization needs GSC impressions and page value, which belong to opportunity detection work in a later packet. Restore the behavior as it was and record the limitation in the report. Do not invent better numbers.

Verify the opportunity unique constraint at `apps/api/app/products/seo/models.py:216` and state what it covers.

### A2. Race condition in `persist_page`

`persist_page` does a non-atomic check-then-insert on `SEOPage`. The engine runs with concurrency > 1, so two workers can both observe `existing_page is None` and both insert, violating `uq_seo_page_normalized_url`.

The constraint `UniqueConstraint("website_id", "normalized_url", name="uq_seo_page_normalized_url")` already exists (`models.py:96`). **No migration is required.**

Replace check-then-insert with a Postgres upsert targeting that constraint — `insert(...).on_conflict_do_update(...)` so a re-crawl refreshes observations rather than silently skipping them, or `on_conflict_do_nothing()` followed by an update if that is cleaner in this codebase. Preserve the current update-on-existing semantics either way: a second crawl must refresh `http_status`, `indexability`, `quality_status`, `technical_issues`, `canonical_url`, and `observed_at`.

---

## B. Crawl correctness gaps

### B1. `Allow` directive unsupported

The robots parser handles `Disallow` only. Per RFC 9309 the most specific matching rule wins, and `Allow` overrides a broader `Disallow`. Implement precedence by longest matching path. Add a test where `Allow: /admin/public` overrides `Disallow: /admin/`.

### B2. `rel="nofollow"` not honored on anchors

Only `<meta robots>` is checked. Individual `<a rel="nofollow">` links must not be enqueued for traversal. They are still recorded as links — nofollow affects traversal, not inventory. Add a test.

### B3. Sitemap-vs-crawl comparison missing

Master Spec 13.45 and the 4A packet both require comparing sitemap URLs against crawl inventory. Sitemaps are discovered and parsed but never compared. Persist or report: URLs in the sitemap not reached by the crawl, URLs crawled but absent from the sitemap, and sitemap URLs that are non-indexable. Add a test.

---

## C. Missing test coverage

Each of these failed audit for absence of a test, not absence of behavior.

1. **SC4A-LIMITS at 250** — packet requires both 25 and 250; only 25 is tested.
2. **SC4A-FIELDS** — `redirect_destination`, `error`, `quality_status`, and `technical_issues` are persisted but never asserted. Add assertions covering all four, including a redirect case and an error case.
3. **SC4A-PARTIAL** — no test that a crawl interrupted by total timeout retains already-fetched pages and terminates `partial` with a reason.
4. **SC4A-IDEMPOTENT at the database level** — current tests only assert engine-level yields. Add a test that runs the same crawl twice and asserts no duplicate `SEOPage` rows and no duplicate active `SEOOpportunity` rows. This also proves A2.
5. **SC4A-TENANT negative** — no test that a cross-organization read of crawl runs or page inventory fails.

Tests requiring the database must actually run. If `LILOS_TEST_DATABASE_URL` is unavailable, say so explicitly and do not report COMPLETE.

---

## D. Reclassified — not defects, do not "fix" with tests

**SC4A-DISCOVERY** and **SC4A-DURABLE** cannot pass in a unit test by construction. They require the migration applied and the API deployed, then a real crawl of `wheylandelectric.com` returning an actual page count, and an observed 202-with-run-reference while the worker progresses.

These remain `IMPLEMENTED_NOT_ACCEPTED` pending live acceptance. Do not write a mock that simulates deployment and call it passing — that would be the same failure mode the packet exists to prevent. Record them as live-acceptance items in the report.

---

## E. Explicitly deferred — do not implement

- **SC4A-STATES browser tests** — the SEO page is being modified concurrently under Packet 4 (`packet/4-product-convergence`). Browser tests written here would conflict. Deferred to Packet 4.
- **`<link rel="alternate">` and `<meta http-equiv="refresh">` extraction** — outside packet scope. Record as future work.

---

## Acceptance

1. Opportunities are created from technical issues on a crawl, deduplicated, with evidence and score explanation. Evidence: test plus the restored code.
2. Concurrent persistence of the same normalized URL cannot violate `uq_seo_page_normalized_url`. Evidence: upsert implementation plus the idempotency test.
3. `Allow` overrides a broader `Disallow` by longest match. Evidence: test.
4. `rel="nofollow"` anchors are recorded but not traversed. Evidence: test.
5. Sitemap-vs-crawl comparison produces the three categories. Evidence: test.
6. All five missing tests exist and pass, database-backed where applicable.
7. Full gate green: `uv run pytest tests/python/seo -v`, `uv run ruff check .`, `uv run mypy apps/api/app/products/seo`, `npm run typecheck`, `npm run test`, `npm run build`, `git diff --check`.
8. No file was rewritten wholesale. Evidence: `git diff --stat` with insertions and deletions roughly proportionate per file.

---

## Report

Use the `AGENTS.md` packet report format, plus:

- Confirmation that opportunity creation is restored, and the scoring limitation stated plainly
- The upsert strategy chosen and why
- `git diff --stat`
- Which tests ran against a real database and which could not
- The two live-acceptance items restated as outstanding
- Anything else found and intentionally not implemented
