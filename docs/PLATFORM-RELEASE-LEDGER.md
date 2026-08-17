# LILOs Platform Release Ledger

This ledger is updated by the principal release integrator from repository and live evidence.

## Status vocabulary

- `NOT_STARTED`
- `IMPLEMENTED_NOT_ACCEPTED`
- `LIVE_READ_ACCEPTED`
- `LIVE_WRITE_ACCEPTED`
- `PILOT_READY`
- `BLOCKED_EXTERNAL`
- `DEFERRED_POST_PILOT`

Do not mark a capability more complete than the available evidence.

## Baseline

**Round 0 verified baseline:**
- Branch: `release/platform-consolidation`
- SHA: `35cf577813480da7869f6917fcf82f2f12a2230e`
- Parent (main): `65c51f4dfd0a3d9a7642a68814a58c21679038eb`
- Working tree: clean
- Migration head: `20260811_0002_gbp_media_safe_error_code` (32 total migrations)
- Vercel deployment: rate-limited (PR #15 deployment blocked; PR #14 deployed successfully)
- Render API/worker/scheduler: deployment parity not verified live (requires runtime access)

## Capability ledger

The **Implementation** column uses the formal status vocabulary. The **Live acceptance**, **UX / productization**, **Automation**, and **Reporting** columns use evidence-backed qualifiers:
- A formal status (e.g., `IMPLEMENTED_NOT_ACCEPTED`) where the column represents a distinct acceptance dimension.
- `n/a` — not applicable to this capability.
- `partial` — some evidence exists but the dimension is not complete (equivalent to `IMPLEMENTED_NOT_ACCEPTED` for that dimension).
- `unknown` — no live evidence available; requires runtime access to verify.

| Layer / capability | Implementation | Live acceptance | UX / productization | Automation | Reporting | Current blocker / evidence |
|---|---|---|---|---|---|---|
| Agency operating layer | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **Packet 4:** Overview prioritizes requires-attention work, omits unknown KPI totals instead of rendering zero, removes duplicated performance/readiness blocks, and links compactly to Insights and Integrations. The visual iteration adds explicit client/all-recorded-activity context, compact action-oriented thin-data states, and separate populated/empty fixture evidence. Fixture-rendered acceptance evidence only; live role/data acceptance remains outstanding. |
| Client workspace | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **Packet 1: Admin nav hidden for clients; unauthorized states on /administration, /onboarding.** Live client-role scoping still unverified without runtime access. |
| Entitlement-aware navigation | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | **Packet 1: Navigation role-aware via `_updateAdminNavigation()` checking platform admin status + membership type.** Backend authorization enforces per-request. |
| Unified onboarding | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | readiness partial | **Packet 2: Three-mode responsibility contract implemented.** `OnboardingOrchestrationService` extended with `managed`/`co_managed`/`self_service` modes over ONE engine. Co-managed step assignments persisted in `onboarding_step_assignments`. Client-facing onboarding API at `/api/v1/client/onboarding/`. Activation fail-closed in both agency and client paths. Frontend mode selector + co-managed assignment controls. Deterministic NULL→managed legacy contract. Auditor review pending. |
| Google connection lifecycle | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync partial | health partial | `GBPConnectionService` handles full OAuth lifecycle with incremental scopes. PR #10 repaired reconnect logic. Live acceptance: healthy connection must not re-prompt OAuth (unverified). |
| Google provider resource mapping | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | **Packets 1/4:** Discovery remains absent from GBP; the existing mapping queue is now privileged, collapsed, and contained in Integrations. API routes/contracts are unchanged. Live mapping acceptance remains outstanding. |
| GBP operational product | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync/media/post workflows partial | partial | **Packet 4:** Confirmed-location operational workspace now exposes profile, hours, posts, and media with one bounded dependency banner and no discovery list. Existing frontend contracts expose no GBP performance or recommendation read model; those sections were not invented. Live provider acceptance remains outstanding. |
| Reviews | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | ingestion/reply workflow partial | partial | **Packet 4:** Compact inbox, status/draft/approve/publish stages, approvals, freshness, and honest “Not classified” sentiment presentation implemented. Live response publish acceptance remains outstanding. |
| Search Console | IMPLEMENTED_NOT_ACCEPTED | unknown | IMPLEMENTED_NOT_ACCEPTED | sync unknown | partial | `SearchConsoleService` with discovery, mapping, sync. `SearchConsoleAdapter` for API calls. Live mapping/sync/freshness unverified. |
| GA4 | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync unknown | IMPLEMENTED_NOT_ACCEPTED | **Packet 4 repository evidence:** Insights consumes the existing 7/28/90-day report, prior-period comparisons, source, freshness, and daily series. Historical live metrics exist, but the current period/comparison contract has not been accepted against a live provider. |
| SEO | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **Packet 4:** Crawl overview/history hierarchy, compact opportunities, evidence-linked detail, and Search Console reporting now reuse the shared Chart.js reporting component. Live crawl/GSC/recommendation lifecycle remains unverified. |
| Content | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **Packet 4:** Opportunity→brief→draft→approve→publish pipeline and truthful transition states implemented; provider configuration is linked to Integrations rather than duplicated. Live publish acceptance and the known business-fact confirmation remain outstanding. |
| Leads | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **Packet 4:** Intake, routing, assignment, lifecycle, and communication history are presented as an operational inbox; setup readiness no longer claims usable when sources are absent. Provider-dispatch semantics for `sent` still require live verification. |
| Integrations control plane | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | health partial | **Packet 4:** Integrations owns connection health, capabilities, mapped-resource freshness, privileged collapsed discovery/mapping, and existing disconnect/remediation actions. Existing Google workspace contracts do not expose a connected-account label, per-capability sync timestamps, or a manual sync endpoint; no UI was fabricated for them. |
| Automation & Agents control plane | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | IMPLEMENTED_NOT_ACCEPTED | IMPLEMENTED_NOT_ACCEPTED | **Packet 4:** Governed automation catalog, schedules, last/next run, run history, failure/recovery status, and compact dependency indicator implemented over the existing workflow API. No retry endpoint exists, so failure rows report eligibility/operator review without a false Retry control. Live schedules/runs remain unaccepted. |
| Insights / reporting | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | scheduled reporting partial/unknown | IMPLEMENTED_NOT_ACCEPTED | **Packet 4:** First viewport now contains period/context, compact comparison KPIs, one section-level source/freshness line, and the primary interactive trend. Insights and SEO consume one shared tree-shaken Chart.js component with round-number axes, six thinned date labels, native hover tooltips, full-card responsive canvas sizing, subtle area fill, accessible summary, and non-interpolated null gaps. The refinement removes redundant hover readouts, formats CTR changes as percentage points, explicitly preserves inverted average-position outcome coloring, and tightens the reporting rhythm. Fixture visual evidence is not live acceptance. |
| Release/production acceptance | IMPLEMENTED_NOT_ACCEPTED | partial | n/a | n/a | n/a | **Vercel deployment rate-limited for current main.** PR #14 deployed successfully. Render API/worker/scheduler parity unverified. Migration head `20260811_0002` deployment status unknown. Backup/restore evidence not verified. |

## Round 0 findings

### Confirmed architecture present
- Full FastAPI modular monolith: 23 service domains + 7 product modules
- Astro frontend: 13 page routes, 47 lib modules
- PostgreSQL-backed workflow engine: 9 registered handlers, worker/scheduler runtime
- Complete auth/authz stack: Supabase JWT, role-based access control, tenant isolation
- Google OAuth lifecycle: incremental scopes, token refresh, credential health
- 32 Alembic migrations covering full schema evolution
- ~150+ Python test files, vitest unit tests, Playwright browser tests
- Render deployment (API, worker, scheduler), Vercel deployment (frontend)

### Confirmed gaps (evidence-backed)

1. **P0 — Client scope leakage:** ✅ **RESOLVED in Packet 1.** `gbp.astro` no longer renders unmapped locations. `InsightsService.summary()` counts only confirmed mapped locations. Navigation Admin group hidden from client users via `hidden` attribute + client-side role check. Administration/onboarding pages render unauthorized state for non-privileged users.

2. **P0 — Contradictory readiness:** ✅ **RESOLVED in Packet 1.** Readiness engine now checks `product.required_integrations`: when all required integrations are connected, `LOCATION_PROFILE_MISSING` becomes a non-blocking warning rather than a blocker. This applies generically to any product with required integrations (GBP, Reviews), not a one-off GBP exception. The `LocationProfile` requirement is preserved as a warning.

3. **P1 — Navigation admin leakage:** ✅ **RESOLVED in Packet 1.** Admin group hidden via `hidden` attribute (removes from accessibility tree). `_updateAdminNavigation()` in `boot.ts` controls visibility based on platform admin status AND agency membership type. Administration page shows unauthorized state for non-privileged users. Backend authorization remains authoritative.

4. **P1 — Insights metric semantics:** ✅ **RESOLVED in Packet 1.** `aggregation_service.py` now filters `GBPLocation` by `mapping_status == "confirmed"`. "Managed locations" count reflects only confirmed mapped locations.

5. **P2 — GA4 period/comparison missing:** Insights page explicitly documents this gap. Reporting API does not return observation window or comparable prior period. Deferred to Packet 6.

6. **P2 — Lead communication status semantics:** `sent` status may mean notification queued rather than provider-dispatched. Handler creates `NotificationDelivery` records; actual dispatch is delegated. Live verification required. Deferred to Packet 5/6.

7. **P2 — No active automation schedules:** 9 handlers registered but no evidence of active `Schedule` rows in database for `gbp.sync` or `reviews.ingest`. Deferred to Packet 5.

8. **P3 — Vercel deployment rate-limited:** Current main deployment blocked. Operational resolution required, not a code fix.

9. **P3 — Render deployment parity unverified:** Cannot confirm API/worker/scheduler are running current SHA without runtime access.

### Highest-risk cross-cutting issues

1. **Client scope leakage (P0):** Must be resolved before any client login is issued. Affects GBP page, Insights aggregation, and navigation.
2. **Contradictory readiness (P0):** Undermines trust in the platform's operational state. Affects all product pages and onboarding.
3. **Shared contract instability:** Navigation, readiness, and aggregation contracts must be frozen before parallel work begins.

## Packet acceptance log

### Packet 0 — Baseline and Contract Map
- Branch / commit: `release/platform-consolidation` / `35cf577`
- Auditor result: PASS (deliverables internally consistent)
- Principal result: ACCEPTED
- Focused checks: Repository structure mapped, domain trace complete, ownership boundaries defined
- Live checks: Not applicable (read-only round)
- Ledger rows changed: All rows updated from evidence
- Remaining blockers: Vercel rate-limit (operational), Render parity unverified (needs runtime access)
- Accepted: yes

### Packet 1 — Platform Information Architecture
- Branch / commit: `release/platform-consolidation` / baseline `600eef8` (working tree, not yet committed)
- Auditor result (initial): ACCEPT (no critical blockers; 3 moderate, 2 minor)
- Auditor result (correction pass): ACCEPT (2 moderate, 1 minor — all addressed)
- Principal result: ACCEPTED
- Focused checks: TypeScript typecheck (0 errors), Python mypy (0 errors), ESLint (0 errors), Ruff (0 errors), Prettier (1 file reformatted), vitest (120 passed), pytest (5 passed, 4 skipped)
- Live checks: Not applicable (no runtime access)
- Ledger rows changed: Agency operating layer, Client workspace, Entitlement-aware navigation, Google provider resource mapping, GBP operational product, Insights/reporting
- Root causes resolved:
  1. P0 Client scope leakage — API-level: `list_org_locations` defaults to `mapping_status="confirmed"`; frontend simplified (no client-side filter needed). Discovery path preserved via `gbp.connect`.
  2. P0 Contradictory readiness — removed one-off `_location_has_integration_profile` helper; replaced with generic `integration_connected`-based check: when all required integrations are connected, `LOCATION_PROFILE_MISSING` is non-blocking.
  3. P1 Navigation admin leakage — Admin navigation now uses ONLY authoritative `_isPlatformAdmin` (from `fetchMyPlatformAdministratorStatus()`), no membership-type allowlist. Admin group starts hidden; no flash.
  4. P1 Insights metric semantics — `gbp.locations` filtered to `mapping_status == "confirmed"` at API and aggregation layers.
- Correction pass changes:
  1. `apps/api/app/routes/gbp.py` — `list_org_locations` hardcodes `mapping_status="confirmed"`; removed `mapping_status` query param
  2. `apps/web/src/pages/gbp.astro` — simplified `renderLocationPicker` (API returns confirmed-only)
  3. `apps/web/src/lib/ui/boot.ts` — `_updateAdminNavigation` only checks `_isPlatformAdmin`
  4. `apps/web/src/lib/ui/boot.test.ts` — test for no-membership-type escalation
  5. `apps/api/app/administration/service.py` — removed `_location_has_integration_profile`; uses `integration_connected` for non-blocking
  6. `tests/python/gbp/test_gbp_api.py` — updated existing test; added data-scope boundary test
  7. `tests/python/insights/test_insights_foundation.py` — structural test for aggregation AND filter
- Ownership exceptions: `apps/web/src/pages/gbp.astro` (Product UX-owned) modified during pre-parallel Packet 1 per explicit authorization
- Deferred findings: `list_accounts` endpoint returns all accounts under `gbp.read` (accounts are parent entities, not location data; noted for Packet 3)
- Remaining blockers: Vercel rate-limit (operational), Render parity unverified, live client-role scoping unverified without runtime access
- Accepted: yes

### Packet 2 — Unified Onboarding

- Branch / commit: `release/platform-consolidation` / base `3c653e27c02b4af86b3867c75cda45533f15961f`
- Auditor result: PENDING (not yet audited)
- Principal result: NOT YET ACCEPTED (awaiting auditor review)
- Focused checks:
  - TypeScript typecheck: 0 errors
  - Python mypy: 0 errors (13 source files checked)
  - Ruff: 0 errors
  - Prettier: formatted
  - vitest: 123 passed (all frontend unit tests)
  - pytest unit: 3 passed (NULL resolution, mode resolution)
  - pytest integration: 8 tests defined (require LILOS_TEST_DATABASE_URL)
- Ledger rows changed: Unified onboarding
- Architecture delivered:
  1. **OnboardingResponsibilityMode** — `managed`, `co_managed`, `self_service` enum over ONE engine.
  2. **Deterministic legacy contract** — NULL `onboarding_mode` resolves to `managed`.
  3. **Persisted co-managed assignments** — `onboarding_step_assignments` table with org-scoped unique constraint.
  4. **Client onboarding API** — `/api/v1/client/onboarding/` routes with proper PlatformAdministrator + membership authorization.
  5. **Client state filtering** — `get_client_state()` filters steps by mode + persisted assignments.
  6. **Self-service org creation** — authenticated users can create/bootstrap their own org with `self_service` mode.
  7. **Activation fail-closed** — both agency and client activation routes use `OnboardingOrchestrationService.get_state()` as authoritative source.
  8. **Frontend** — mode selector in create-org form, mode badge in workspace, co-managed step assignment dropdowns.
- Changed files (14 files):
  - `migrations/versions/20260812_0002_onboarding_responsibility_mode.py` (new)
  - `apps/api/app/onboarding/models.py` (new — `OnboardingStepAssignmentRecord`)
  - `apps/api/app/onboarding/contracts.py` (extended)
  - `apps/api/app/onboarding/service.py` (rewritten)
  - `apps/api/app/onboarding/__init__.py` (exports updated)
  - `apps/api/app/routes/client_onboarding.py` (new)
  - `apps/api/app/routes/platform_administration.py` (extended)
  - `apps/api/app/main.py` (router registered)
  - `apps/api/app/organizations/models.py` (+`onboarding_mode` column)
  - `apps/api/app/organizations/contracts.py` (+`onboarding_mode` fields)
  - `apps/api/app/organizations/service.py` (passes through `onboarding_mode`)
  - `apps/web/src/lib/platform-admin.ts` (new types + functions)
  - `apps/web/src/pages/onboarding.astro` (mode selector, assignments UI)
  - `tests/python/onboarding/test_service.py` (extended: 3 unit + 8 integration)
- Cross-workstream: No Integration (`apps/api/app/integrations/`) or Automation (`apps/api/app/execution/`,`worker/`,`scheduler/`) files modified.
- Deferred: Co-managed step assignment UI needs live DB for integration tests; mode-change dropdown on workspace header not yet added (HTML badge exists, no interactive mode-change control yet).
- Remaining blockers: Auditor review pending. Integration tests require `LILOS_TEST_DATABASE_URL`.
- Accepted: no (auditor pending)

### Packet 9D — SEO Crawl Column-Length Overflow

- Branch / SHA: `packet/9d-column-lengths` / pending (not committed)
- Auditor result: NOT RUN
- Principal result: IMPLEMENTED_NOT_ACCEPTED
- Focused checks: `uv run ruff format --check` PASS, `uv run ruff check` PASS, `uv run mypy` PASS, `uv run pytest` (seo + migration + audit suites) 68 passed.
- Root cause: `h1` extraction used `start + absolute_close_index` (adding an absolute index as a relative offset), capturing the entire tag-stripped page body instead of just the `<h1>` text. Real site yielded h1 values 3,001–7,691 characters, exceeding `varchar(2000)`. One overflow value aborted the entire crawl — zero pages persisted.
- Fix category — content: title, meta_description, h1 truncated at ingest to 2000 characters with explicit `…[truncated]` marker and `*_truncated` technical issue.
- Fix category — URLs: four URL columns widened to `text` (migration `20260817_0001` with expand-and-contract documented). Crawler enforces `MAX_URL_LENGTH = 2048`; over-long page URL skipped with reason. Btree index `uq_seo_page_normalized_url` verified with a 2051-character URL insert.
- Resilience: each page persists inside its own savepoint; a failing page rolls back its own savepoint and the crawl continues.
- Regression test: database-backed crawl with over-length title (6,200 chars), meta_description (7,000 chars), and h1 (6,000 chars) completes `status: success`, persisted values are truncated to 2,000 with marker, no `page_failures`. Fails against pre-fix main.
- Adjacent work discovered: the `h1` extraction slice bug (`start + abs_index`) was the root cause producing the absurd h1 values; fixed here because it is the same signal-extraction surface as the truncation work.
- Files changed: `crawl_engine.py`, `service.py`, `models.py`, migration `20260817_0001`, `test_crawl_engine.py`, `test_seo_api.py`, `PLATFORM-RELEASE-LEDGER.md`, new packet doc `PACKET-9D-COLUMN-LENGTHS.md`.
- Remaining risks: none identified; content truncation + URL widening + per-page savepoint provide defence-in-depth. Downgrade of migration restores `varchar(2000)` and fails loudly if a 2001–2048 char URL was persisted, which is acceptable (fail-loud over silent data loss).

---

### Packet 4 — Operational Product Convergence and Design System

- Branch / base: `packet/4-product-convergence` / `01e733e1bc786a3fb141f00c74befb9c07de7b1b` (working tree; not committed)
- Auditor result: NOT RUN
- Principal result: IMPLEMENTED_NOT_ACCEPTED (fixture visual evidence is not live acceptance)
- Focused checks: Packet 4 targeted Vitest checks cover Chart.js input models preserving null gaps, round-number axis bounds, accessible trend summaries, thin-summary KPI handling, status language, design-system data display, and content standards; fixture response modules pass Astro/TypeScript checking.
- Full checks: ESLint + Stylelint + Ruff passed; Astro check 0 diagnostics across 142 files; mypy 441 files; Vitest 206 passed; pytest 375 passed / 395 skipped / 1 dependency warning; Astro build 14 pages; Playwright 184 passed across desktop/mobile; fixture-backed visual regression 10 passed; `git diff --check` passed.
- Screenshot evidence: `docs/packets/evidence/packet-4/` (all images visibly captioned fixture-rendered/not live; required desktop captures are 1440×900 and mobile is 390×844). The chart-refinement captures show full-card Analytics/Search Console canvases, compact vertical rhythm, percentage-point CTR delta, and explicitly inverted average-position styling; populated and empty Overview captures remain included.
- Section 7 defect remediation: shared PageSection, Notice, Badge, CardGrid, disabled Button, DataTable, and mobile PageHeader contracts now resolve the systemic duplication, collision, stretching, orphan-card, list-alignment, and responsive-composition defects without page-local style exceptions. Overview thin data is one invitation with one action; Content has one primary tab row; Leads omits contract-only identifiers and uses user-facing unavailable language; Business Profile renders only confirmed mapping, write authority, discovery/sync freshness, posts, media, and special-hours values exposed by existing response contracts.
- Chart addendum acceptance: the shared Insights/SEO Chart.js theme uses a data-near round-number floor (without forcing zero), chart-area-aware responsive gradient, unboxed x labels, subtle vertical guides, a dominant plot, and a 2.5px line. Rendered-canvas pixel samples at top/middle/bottom produced alpha values `56/32/9` at 1440px, remained `56/32/9` after a 1440→1100→1440 responsive resize, and matched on SEO, verifying the gradient from rendered pixels rather than configuration.
- Fixture boundary: `apps/web/tests/fixtures/packet-4/`, gated by `LILOS_PACKET4_FIXTURES=1`, loopback-only, development-server-only, not imported by production modules, absent from the deployed build, and performs no database/provider writes. `visual-server.mjs` owns Astro and the evidence proxy in one test-only lifecycle.
- Design-system enforcement: the confirmed token layer and shared primitives now compose all ten Packet 4 surfaces; the source audit is 57/57 raw hex values, 42/42 arbitrary spacing declarations, and 31/31 inline styles replaced. Stylelint rejects new raw hex and literal-unit spacing outside `tokens.css`; ESLint rejects Astro inline style attributes; deterministic 1440×900 Playwright baselines cover every Section 7 surface.
- Workspace audience: membership/scope is authoritative. `internal`, `partner`, and `support` render **Agency workspace**; client membership types render **Client workspace**. Packet 4 fixture evidence uses an internal membership and therefore correctly renders **Agency workspace**.
- Ledger rows changed: Agency operating layer; Google provider resource mapping; GBP operational product; Reviews; GA4; SEO; Content; Leads; Integrations control plane; Automation & Agents control plane; Insights / reporting.
- Ownership exceptions reported: principal-owned Overview, Settings, shared operating-dashboard/UI primitives, Administration, Onboarding, and release ledger; Integrations-owned page; Automation-owned page; Insights-owned page. These were the packet's explicit cross-surface status-ownership, presentation, raw-enum, state/recovery, and ledger scope. No backend-owned files changed.
- Contract-backed gaps intentionally not fabricated: Google connected-account label, per-capability sync timestamps, and manual sync action; GBP current core profile values, address, and regular weekly-hours read models; lead source identity/name and service name (the list/detail contracts expose only IDs); automation retry action.
- Live checks: not run; screenshots use explicitly authorized contract-shaped visual fixtures only.
- Accepted: no (live provider/role acceptance and principal/auditor review remain outstanding)

---

## Known baseline questions — Round 0 answers

| Question | Answer |
|----------|--------|
| Exact current main SHA and clean/dirty state | Branch `release/platform-consolidation`, SHA `35cf577`, clean tree. Parent main at `65c51f4`. |
| Exact frontend/API/worker/scheduler deployed SHAs | Not verifiable without runtime access. PR #14 Vercel deployment green. PR #15 Vercel rate-limited. Render parity unknown. |
| Current migration head and deployed DB migration state | Head: `20260811_0002_gbp_media_safe_error_code`. Deployed DB state unknown without runtime access. |
| Real agency-role and real client-role navigation/scoping | Not tested live. Code inspection shows Admin group hidden via `hidden` attribute (frontend-only). |
| Whether client users can see unrelated Google provider resources | **High risk: YES, based on code inspection.** `gbp.astro` renders all unmapped locations. Live client-role test required. |
| Source and semantics of "17 locations" metric | `InsightsService.summary()` counts ALL `GBPLocation` rows for org, including unmapped. Likely includes non-Wheyland resources from agency Google credential. |
| Source of contradictory "Create the location profile" readiness | `AdministrationService.readiness()` checks `LOCATION_PROFILE_MISSING` independently of GBP sync state. Location profile may exist but not be linked to GBP location. |
| Current Google granted capabilities | Not verifiable without runtime access. Code supports GBP + GSC + GA4 scopes. |
| Current GSC and GA4 confirmed mappings, sync timestamps | Not verifiable without runtime access. GA4 metrics visible in screenshots. GSC state unknown. |
| Current workflow/schedule catalog and active handlers | 9 handlers registered. No evidence of active `Schedule` rows in database. |
| Lead email/SMS actual provider-dispatch and delivery semantics | `LeadCommunication.status` supports planned→queued→sent→delivered. Handler sets `sent_at` but delegates dispatch to notification delivery jobs. Live verification required. |
| Current reporting read models and period/comparison/freshness | `InsightsService.summary()` aggregates real data. GA4 metrics lack period/comparison. `MetricObservation.quality_state` enum supports data-quality states. |
| Current release-gate failures and genuine external blockers | Vercel rate-limit (operational). No code-level release gate failures identified. |
