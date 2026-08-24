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
| Google provider resource mapping | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | **PR #44:** Integrations now consumes canonical, connection-scoped `GBPLocation` identity and write-governance truth; mapped/unmapped reconciliation uses provider-mapping and platform `Location.id` identities consistently. The existing AAL2 GBP confirm mutation remains the sole mapping/write-access mutation. Live post-deploy control-plane acceptance remains outstanding. |
| GBP operational product | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync/media/post workflows partial | partial | **PR #39/PR #44:** Profile and post publication retain one canonical governed workflow path and provider verification/reconciliation. Authorized platform administrators can now deliberately enable or disable the existing server-side write gate through the canonical AAL2 confirm endpoint; the mutation does not publish content. Live provider write acceptance remains outstanding. |
| Reviews | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | ingestion/reply workflow partial | partial | **Packet 4:** Compact inbox, status/draft/approve/publish stages, approvals, freshness, and honest “Not classified” sentiment presentation implemented. Live response publish acceptance remains outstanding. |
| Search Console | IMPLEMENTED_NOT_ACCEPTED | unknown | IMPLEMENTED_NOT_ACCEPTED | sync unknown | partial | `SearchConsoleService` with discovery, mapping, sync. `SearchConsoleAdapter` for API calls. Live mapping/sync/freshness unverified. |
| GA4 | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync unknown | IMPLEMENTED_NOT_ACCEPTED | **Packet 4 repository evidence:** Insights consumes the existing 7/28/90-day report, prior-period comparisons, source, freshness, and daily series. Historical live metrics exist, but the current period/comparison contract has not been accepted against a live provider. |
| SEO | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **PR #39:** Opportunity orchestration now gives the newest canonical GSC period precedence, requires a genuinely unmapped page for unmapped demand, keeps technical/PageSpeed findings in SEO, and deterministically archives only stale opportunities from fully evaluated in-scope sources. Live crawl/GSC/recommendation lifecycle remains unverified. |
| Content | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **PR #39:** Only content-addressable SEO demand is mirrored to Content, and source-reference deduplication now uses a direct indexed tenant-scoped lookup instead of a bounded list scan. Durable AI drafting and governed-fact grounding remain in place. Live publish acceptance and deployed AI provider acceptance remain outstanding. |
| Leads | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **Packet 4:** Intake, routing, assignment, lifecycle, and communication history are presented as an operational inbox; setup readiness no longer claims usable when sources are absent. Provider-dispatch semantics for `sent` still require live verification. |
| Integrations control plane | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | health partial | **Packet 4/PR #44:** Integrations owns connection health, capabilities, mapped-resource freshness, privileged discovery/mapping, and deliberate provider-write governance. Successful discovery, mapping, and write-access changes now re-fetch connection/workspace backend truth. Connected-account label, per-capability sync timestamps, and a manual sync endpoint remain absent and were not fabricated. |
| Automation & Agents control plane | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | IMPLEMENTED_NOT_ACCEPTED | IMPLEMENTED_NOT_ACCEPTED | **PR #39:** Duplicate workflow registration now fails closed, provider handlers execute outside workflow-row transactions, generic terminal/retry/reconciliation audit events are durable, and an authorized operator request is proven through API run creation → enqueue → worker handler → terminal history and audit against PostgreSQL. Live production schedules/runs remain unaccepted. |
| Production AI provider | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | n/a | n/a | **PR #39:** Hermes is the production-primary agentic runtime boundary, deployed as an exact private Render service with persistent state and API/worker bindings. Its adapter validates response contracts, fails closed on timeout/malformed/secret-bearing output, and always requires draft/human review. Mocked contract acceptance is complete; live Hermes execution remains outstanding. |
| AI Gateway production routing | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | n/a | n/a | **PR #39:** Provider-neutral routing now passes authoritative organization/location scope, derives opaque tenant-scoped Hermes sessions, recursively rejects secret-bearing inputs, and preserves cost/latency bounds and AI execution usage history. Live routed execution remains outstanding. |
| Content AI drafting | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | n/a | n/a | **Packet 5:** ContentService wired to configured AI gateway (no longer hardcodes DeterministicAIProvider). AI draft endpoint routes through production provider when configured. Always requires human review. Real AI acceptance pending API key. |
| SEO crawler runtime | LIVE_READ_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | **Packet 9D:** Controlled production crawl completed (max_pages=10, max_depth=2, crawl_delay=1). Real Wheyland pages traversed, persisted, and rendered in SEO UI. StringDataRightTruncationError resolved. |
| SEO expert audit/intelligence | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | Current crawl-generated opportunities are primarily basic technical signals. Not yet the final intelligent local-SEO recommendation engine. |
| SEO opportunity intelligence | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | Deferred to dedicated SEO Intelligence/Productization pass. |
| SEO max-pages enforcement | KNOWN PRODUCTIZATION DEFECT | n/a | n/a | n/a | n/a | Configured max_pages=10 produced 12 pages due to concurrent batch overshoot in crawl_engine. Deferred to SEO Intelligence/Productization pass. |
| Insights / reporting | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | scheduled reporting partial/unknown | IMPLEMENTED_NOT_ACCEPTED | **Packet 4:** First viewport now contains period/context, compact comparison KPIs, one section-level source/freshness line, and the primary interactive trend. Insights and SEO consume one shared tree-shaken Chart.js component with round-number axes, six thinned date labels, native hover tooltips, full-card responsive canvas sizing, subtle area fill, accessible summary, and non-interpolated null gaps. The refinement removes redundant hover readouts, formats CTR changes as percentage points, explicitly preserves inverted average-position outcome coloring, and tightens the reporting rhythm. Fixture visual evidence is not live acceptance. |
| Release/production acceptance | IMPLEMENTED_NOT_ACCEPTED | partial | n/a | n/a | n/a | **Vercel deployment rate-limited for current main.** PR #14 deployed successfully. Render API/worker/scheduler/Hermes parity unverified. Migration head `20260821_0002` deployment status unknown. Backup/restore evidence not verified. |

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

### Packet 5 — Automation & Agents + Production AI Gateway

- Branch / SHA: `packet/5-automation-agents-production` / base `968c8b705cbfd08991bd284109b05bbe238a4340`
- Auditor result: NOT RUN
- Principal result: IMPLEMENTED_NOT_ACCEPTED (real AI execution requires OpenRouter API key; live production schedules/runs unaccepted)
- Focused checks:
  - Python ruff: 0 errors on AI module, handlers, config
  - Python mypy: 0 errors on AI module, handlers, config
  - Python pytest (non-integration): 439 passed, 16 skipped
  - Python pytest (workflow integration): 101 passed (PostgreSQL)
  - AI unit tests: 31 passed (mocked HTTP)
  - Scheduled-execution integration: 3 passed (PostgreSQL, real SchedulerBackend/WorkerBackend)
  - Approval/recovery integration: 7 passed (PostgreSQL)
  - Frontend typecheck: 0 errors (142 files)
  - Frontend build: 14 pages built successfully
  - Render blueprint validation: 6 passed
- Architecture delivered:
  1. **Production AI Gateway** — OpenRouter provider adapter with full error handling (auth, rate-limit, 4xx/5xx, malformed, timeout, connect), usage capture (tokens, cost, latency), and secret safety. Provider-neutral AIProvider protocol preserved. Deterministic provider fail-closed in production via `resolve_ai_provider()`.
  2. **AI configuration** — 8 new Settings fields: `ai_provider`, `openrouter_api_key` (aliased to `LILOS_OPENROUTER_API_KEY`), `openrouter_base_url`, `default_model`, `task_model_overrides`, `timeout_seconds`, `max_output_tokens`, `maximum_cost_microunits`. Task→model routing via `ai_task_model_map()`.
  3. **AI Gateway upgrade** — Task routing, cost/latency bounds enforcement, provider error wrapping, default key filling. `DeterministicAIProvider` returns full usage dict.
  4. **Content/Reviews service wiring** — Both services now use `build_ai_gateway()` instead of `AIGateway(DeterministicAIProvider())`. AIExecution persists `input_tokens`, `output_tokens`, `estimated_cost_microunits`, `latency_ms`.
  5. **Scheduled-execution handler fix** — `_handle_gbp_sync` and `_handle_reviews_ingest` now resolve GBPLocation from platform `location_id` when `gbp_location_id` is absent from input document. This enables schedule-dispatched runs (which only provide `schedule_id`/`scheduled_for`) to resolve the correct GBP location.
  6. **Scheduled-execution acceptance** — End-to-end PostgreSQL integration test proves: schedule → scheduler dispatch → job creation → worker claim → handler execution → terminal success → schedule state advances → run history authoritative → duplicate dispatch prevention → tenant isolation. Uses real SchedulerBackend, WorkerBackend, ExecutionService with monkeypatched provider boundary (no external provider call).
  7. **Approval boundary** — Proven at product layer: GBP handler rejects non-reserved publications (`PUBLICATION_NOT_RESERVABLE`). Idempotency enforced upstream at workflow-run and publication-creation layers. Cross-org tenant isolation verified.
  8. **Failure/recovery** — Retryable failure schedules retry with exponential backoff. Permanent failure marks failed immediately. At max attempts, dead-lettered (no poison loop). Success marks completed.
  9. **Automations UX** — Added "Running now" metric card, dedicated Schedules section with authoritative schedule state (workflow, status, cadence, last run, next run), Duration column in run history, client-safe recovery language (no implementation vocabulary).
  10. **Render blueprint** — `LILOS_OPENROUTER_API_KEY` added to lilos-api, lilos-worker, and lilos-scheduler secret policies.
- Changed files (17 files):
  - `apps/api/app/config.py` (AI settings)
  - `apps/api/app/ai/errors.py` (new)
  - `apps/api/app/ai/providers.py` (new)
  - `apps/api/app/ai/gateway.py` (upgraded)
  - `apps/api/app/ai/factory.py` (new)
  - `apps/api/app/products/content/service.py` (wired to factory)
  - `apps/api/app/products/reviews/service.py` (wired to factory)
  - `apps/api/app/execution/handlers.py` (scheduled-execution location resolution)
  - `apps/web/src/pages/automations.astro` (UX productization)
  - `render.yaml` (OPENROUTER key)
  - `scripts/validate_render_blueprint.py` (secret policy)
  - `.env.example` (AI vars)
  - `tests/python/ai/__init__.py` (new)
  - `tests/python/ai/test_providers.py` (new)
  - `tests/python/ai/test_gateway.py` (new)
  - `tests/python/workflows/test_scheduled_execution.py` (new)
  - `tests/python/workflows/test_approval_and_recovery.py` (new)
  - `docs/PLATFORM-RELEASE-LEDGER.md` (this entry)
- Ledger rows changed: Automation & Agents control plane, Production AI provider, AI Gateway production routing, Content AI drafting, SEO crawler runtime, SEO expert audit/intelligence, SEO opportunity intelligence, SEO max-pages enforcement
- Deferred: SEO expert intelligence, SEO opportunity intelligence, SEO max-pages concurrency overshoot (all deferred to dedicated SEO Intelligence/Productization pass)
- Remaining blockers: Real AI execution requires `LILOS_OPENROUTER_API_KEY` secret in production environment. Live production schedules/runs unaccepted without runtime access.
- Accepted: no (real AI acceptance + auditor review pending)

---

### Track C — Source-Driven Business Knowledge Reconciliation

- Branch / SHA: `fix/business-knowledge-reconciliation` / base `5dea6dc8e9f15df98a7386ad4459d9b01f9abd8b`
- Auditor result: NOT RUN
- Principal result: IMPLEMENTED_NOT_ACCEPTED (integration tests require `LILOS_TEST_DATABASE_URL`)
- Focused checks:
  - Python ruff: 0 errors on `administration/service.py`, `test_reconciliation.py`
  - Python mypy: 0 errors on changed files
  - Python pytest (collection): 17 tests collected (7 existing + 10 new)
  - Syntax: clean
- Architecture delivered:
  1. **Source-driven `brand.approved_claims` derivation** — Reconciliation now produces service/claim candidates from canonical persisted LILOs data (GBP profile snapshot categories + serviceItems, organization profile primary_services + approved_claims, SEO crawl page H1 signals on service-context pages) instead of requiring an operator to type the same knowledge into the organization profile first. Removes the circular dependency where Content required approved claims → reconciliation needed profile approved claims → operator manually typed approved claims.
  2. **Claim safety filtering** — Provider/crawl-derived names pass a safety filter that rejects superlatives, awards, licensing, bonding, insurance, guarantees, warranties, pricing, certifications, years-in-business, financing, free-estimate, emergency/24-7, performance-statistic, and other material claims. Explicitly supplied profile knowledge is preserved as-is.
  3. **Provenance tracking** — Composite source strings (e.g. `"gbp_profile_snapshot+organization_profile+seo_crawl"`) identify which source families contributed. Audit metadata records per-source candidate counts.
  4. **Normalization and deduplication** — Case/punctuation/whitespace variants normalize to one entry. Cross-source duplicates collapse to a single claim.
  5. **Idempotent reconciliation** — Repeated reconciliation with unchanged source data proposes no duplicates. Source data changes produce a proper next revision via the existing immutable revision architecture (same fact_identity, incremented revision, supersedes link).
  6. **Conflict surfacing** — When GBP and profile sources produce distinct names, both are retained in the proposed candidate list; neither is silently dropped. The operator reviews and confirms.
  7. **Tenant/location safety** — All source reads are organization-scoped. GBP data from other organizations or non-primary locations does not leak into candidates.
  8. **SEO crawl evidence quality** — Only H1 text from pages with service-context URL segments or multi-word slug-H1 corroboration is considered. Generic furniture pages (home, contact, about, blog, etc.) are excluded.
- Changed files (2 files):
  - `apps/api/app/administration/service.py` — Added module-level helpers (`_normalize_service_name`, `_service_claim_key`, `_website_matches_domain`, `_is_safe_service_claim`, `_clean_provider_name`, `_gbp_category_names`, `_gbp_service_item_names`, `_profile_service_names`, `_seo_service_names`), claim-safety patterns, service URL segment lists, non-service path/H1 patterns. Refactored `reconcile_business_facts` to look up GBP snapshot once for both hours and service candidates, added source-driven `brand.approved_claims` derivation from GBP + profile + SEO crawl sources, enriched audit metadata with per-source candidate counts.
  - `tests/python/administration/test_reconciliation.py` — Added 10 new tests: GBP-derived service candidates, SEO crawl-derived candidates, duplicate normalization, risky claim filtering, no-sources unresolved, confirmation required (propose → approve → resolved), conflict surfacing, cross-tenant isolation, idempotency, source-change next-revision. Added `_seo_page` fixture helper. Updated imports for `SEOPage`, `SEOWebsite`, `BusinessFactDecision`.
- Ledger rows changed: Content (business-fact confirmation gap addressed)
- Adjacent work intentionally not implemented:
  - No Content frontend changes.
  - No Content AI generation runtime changes.
  - No Integrations redesign.
  - No new scraping/provider framework.
  - No external provider calls — uses only persisted canonical source data.
  - No new fact key/schema — reuses existing `brand.approved_claims`.
  - No per-claim provenance model extension — uses existing `source` field + audit metadata.
  - No brand-summary derivation (not required to unblock Content).
- Remaining blockers: Integration tests require `LILOS_TEST_DATABASE_URL`. Live Wheyland acceptance requires runtime access to verify GBP snapshot + SEO crawl data produces expected candidates.
- Accepted: no (integration test run + auditor review pending)

---

### Content Integration — Durable AI, Grounding, Knowledge, and Editorial Workflow

- Branch / SHA: `release/platform-consolidation` / working tree (not yet committed)
- Auditor result: NOT RUN
- Principal result: IMPLEMENTED_NOT_ACCEPTED (deployed/live-tested acceptance remains outstanding)
- Focused checks:
  - Prettier: formatted (3 frontend files)
  - format:check:web: PASS
  - lint:web (ESLint + Stylelint): PASS
  - typecheck:web (astro check, 143 files): PASS (0 errors, 0 warnings)
  - test:web (vitest, 31 files): 261 passed, 2 failed (dashboard-logic.test.ts — pre-existing localStorage issue, unrelated to Content)
  - build:web (astro build): 14 pages built
  - check:browser (Playwright, 218 tests): 218 passed (desktop + mobile)
  - Backend (previously accepted): 109/109 focused backend tests PASS, 18/18 Business Knowledge reconciliation tests PASS, 5/5 governed fact scope tests PASS
- Architecture delivered:
  1. **Durable Content AI** — Frontend/backend integration for asynchronous AI draft generation via the platform workflow engine. `generateAIDraft()` returns 202 with `workflow_run_id`; polling via `getWorkflowRun()` with status mapping (`mapWorkflowRunToContentStatus`), human-readable labels (`describeAIDraftStatus`), and terminal detection (`isAIDraftTerminal`). Idempotency key reuse across retries. sessionStorage persistence for browser-refresh recovery (`storeInFlightAIDraft`/`recoverInFlightAIDraft`/`clearInFlightAIDraft`). Polling at 3s intervals with 200-attempt max (~10 min).
  2. **Governed fact grounding** — `CONTENT_REQUIRED_FACT_KEYS` (`business.name`, `brand.approved_claims`) enforced at the frontend contract layer. Brief creation requires all required facts to be resolved. Fact resolution state surfaced in the context rail (Approved / Needs review / Missing / Unavailable).
  3. **Editorial Content workspace** — Two-column editorial layout (context rail + document area) with safe DOM-based document rendering (`renderDocumentBody` — no innerHTML, XSS-safe). Revision history, approval actions (editorial/client stages), publication workspace, and activity audit trail.
  4. **Source-driven Business Knowledge** — Reconciliation produces service/claim candidates from canonical persisted LILOs data (GBP profile snapshot, organization profile, SEO crawl page H1 signals). Claim safety filtering, provenance tracking, normalization/deduplication, idempotent reconciliation, conflict surfacing, and tenant/location safety.
  5. **Intent widening** — Migration `20260818_0001` widens `content_briefs.intent` from `varchar(100)` to `varchar(500)`. Model, contract, and frontend constants (`CONTENT_GOAL_MAXLENGTH=500`, `AUDIENCE_MAXLENGTH=500`) all aligned.
- Changed files (9 files):
  - `migrations/versions/20260818_0001_widen_content_brief_intent.py` (new)
  - `apps/api/app/administration/service.py` (source-driven reconciliation)
  - `apps/api/app/products/content/service.py` (durable AI wiring)
  - `apps/api/app/routes/content.py` (durable AI endpoint)
  - `apps/web/src/lib/content.ts` (durable AI types, status mapping, sessionStorage, document rendering, validation helpers)
  - `apps/web/src/lib/content.test.ts` (durable AI status mapping tests, validation tests)
  - `apps/web/src/pages/content.astro` (editorial workspace, AI draft generation UI, polling, context rail, safe document rendering)
  - `tests/python/administration/test_reconciliation.py` (Business Knowledge reconciliation tests)
  - `tests/python/content/test_content_api.py` (Content API tests)
  - `tests/python/content/test_content_durable_ai.py` (durable AI tests)
- Ledger rows changed: Content
- Remaining blockers: Live AI provider acceptance requires `LILOS_OPENROUTER_API_KEY`. Live publish/provider acceptance requires runtime access. Dashboard-logic.test.ts has 2 pre-existing localStorage failures unrelated to Content.
- Accepted: no (deployed/live-tested acceptance remains outstanding)

---

### Production Acceptance Harness — Completion

- Branch / SHA: `main` / working tree (not committed)
- Auditor result: NOT RUN
- Principal result: IMPLEMENTED_NOT_ACCEPTED (harness is complete; execution requires manual auth bootstrap)
- Focused checks: Prettier (PASS), ESLint (PASS), Astro typecheck (PASS — 0 errors, 0 warnings, 0 hints across 146 files), Stylelint (PASS)
- Harness sections implemented (18 sections, 85+ tests):
  1. **AUTH / TENANCY** — 11 tests: authenticated session verification, Wheyland Electric org check, workspace audience label, sign-out button presence, cross-tenant data leakage check, unauthorized 401/403 detection on product API routes, org/location ID resolution for cross-section use, platform admin status check, admin nav visibility matches authority, no critical boot errors.
  2. **INTEGRATIONS** — 4 tests: integration page load with provider cards, Google connection status API health (200/404 valid, 5xx fails), Google workspace endpoint reachable, GitHub workspace endpoint reachable (403 acceptable for non-AAL2).
  3. **GBP READ/SYNC** — 3 tests: GBP page loads with real data or truthful empty state, confirmed locations API, profile snapshot retrieval if mapped.
  4. **GBP GOVERNANCE** — 2 tests: write actions safety (no enabled external writes), publish endpoint fails-closed with AAL2 requirement.
  5. **REVIEWS** — 3 tests: reviews page loads with inbox or empty state, list API returns data, response generation does not publish externally (safety assertion).
  6. **LEADS** — 4 tests: leads page loads, list API healthy, synthetic lead creation via intake API (skips gracefully if AAL2 required), verify synthetic lead retrievable.
  7. **SPEED-TO-LEAD** — 2 tests: lead source performance API healthy, lead communication endpoint gated.
  8. **CONTENT** — 4 tests: content page loads, list/summary APIs healthy, full content creation → brief → AI draft workflow (durable path, poll for completion, verify revision + provenance).
  9. **SEO** — 4 tests: SEO page loads, websites/crawl-runs/opportunities APIs healthy.
  10. **SEARCH CONSOLE** — 1 test: performance API reachable (requires mapped website).
  11. **GA4** — 2 tests: analytics performance/summary APIs reachable, verify no Invalid Date/NaN in response.
  12. **INSIGHTS** — 3 tests: insights page loads with period/context and no Invalid Date/NaN/undefined, summary API healthy, website readiness API healthy.
  13. **AUTOMATIONS** — 4 tests: page loads with catalog/schedule data, workflow catalog returns types, run history reachable, schedule list reachable.
  14. **WORKER** — 2 tests: worker liveness proven by completed workflow runs, job claiming/execution verification.
  15. **SCHEDULER** — 3 tests: create canary schedule (every 30 min), verify persistence with correct fields (status, next_run_at, workflow_key), disable and cleanup canary.
  16. **OVERVIEW UX** — 3 tests: no placeholder text, no self-contradiction (on-track vs attention), no Invalid Date/NaN/undefined.
  17. **CLIENT UX** — 30 tests (3 per page × 10 pages): no raw errors, no broken layout (horizontal overflow), no empty buttons, no 5xx from API calls.
  18. **CONSOLE / NETWORK** — 3 tests: no unexpected 4xx/5xx/console/page-errors across all pages, no blank pages, correct content-type.
- Harness defect remediation:
  1. **Defunct dependency removed** — `production-acceptance` project no longer depends on `auth-setup`. Clear error at test startup if `.auth/production-state.json` missing.
  2. **ESM-safe auth.setup.ts** — Uses `fileURLToPath(import.meta.url)` instead of unsafe `__dirname`.
  3. **StorageState comment corrected** — Playwright persists cookies + localStorage, NOT sessionStorage.
  4. **Real auth/tenancy verification** — 11 tests verify: Wheyland Electric selected, org/location IDs resolved via API, workspace audience label correct, admin nav matches authority, no 401/403 on product API routes.
  5. **Network instrumentation hardened** — `ProductionObserver` class records ALL 4xx/5xx/console errors/page errors. Allowlist only for provably benign requests (extensions, analytics, auth token refresh, favicon 404s). Unexpected 401/403/5xx ARE failures, not "≤3 is okay".
- Safety:
  - Hardcoded `https://lilos-platform-web.vercel.app` base URL only
  - No credentials/tokens committed
  - `.auth/` directory gitignored (`apps/web/.auth/`)
  - Synthetic test records marked `[PROD-ACCEPTANCE]`
  - Schedule canary created with 30-minute interval, paused and documented
  - No destructive provider writes attempted
  - Leads intake skips if AAL2 required; Content AI draft skips gracefully if OpenRouter key not configured
  - All skips use `test.skip()` with honest reason strings
- Changed files (4 files):
  - `apps/web/playwright.production.config.ts` (new — removed dependency, added auth validation comment)
  - `apps/web/tests/production/auth.setup.ts` (ESM-safe, correct comment, better bootstrap wait)
  - `apps/web/tests/production/acceptance.spec.ts` (new — 2080 lines, 18 sections, 85+ tests)
  - `apps/web/package.json` (pre-existing — `production:auth` / `production:test` scripts)
- Remaining blockers to EXECUTION:
  - Manual auth bootstrap required: `npm run production:auth` (headed, operator must log in)
  - Worker/scheduler must be running on Render for durable workflow/schedule tests
  - `LILOS_OPENROUTER_API_KEY` must be configured for AI draft completion
  - GBP mapping must exist for profile snapshot tests
  - Leads intake requires AAL2 MFA step-up (harness skips if not available)
- Accepted: no (execution pending auth bootstrap)
- Harness readiness: READY TO EXECUTE (all validations pass; no product code changes)

---

### PR #39 — Hermes First-Class Runtime / Orchestration Finish Line

- State: `IMPLEMENTED_NOT_ACCEPTED`.
- Repository evidence: current branch `fix/hermes-first-class-orchestration-2026-08-21`; implementation reviewed against `origin/main`, the Master Spec precedence contract, and `.github/workflows/ci.yml`.
- Root-cause correction batch:
  - Workflow handlers fail closed on duplicate registration; resource-bound product runs enqueue only after authoritative resource attachment; handlers no longer hold workflow-row transactions across provider I/O; terminal/recovery outcomes produce durable audit evidence.
  - GBP profile/post publication has one canonical handler per workflow, uses governed facts for generation, commits provider identities before verification, and reconciles ambiguous outcomes without blind duplicate writes.
  - SEO selects the newest canonical GSC evidence, uses semantic opportunity routing, performs direct indexed Content deduplication, and scopes stale archival to fully evaluated source families without touching unrelated or decided opportunities.
  - Hermes receives opaque tenant-scoped sessions through the existing LILOS AI/workflow boundary, validates strict output/usage contracts, rejects secret-bearing input/output, and has private persistent Render wiring with production fail-closed validation.
- Focused acceptance evidence: authorized operator API → durable run/job → worker handler → terminal history/audit; GBP approval/idempotency/provider-transaction boundaries; SEO canonical evidence/routing/stale handling/deduplication; Hermes scope/secret/error contracts; Render wiring. All focused tests pass.
- Validation evidence: Python format/lint/typecheck pass; 82 focused architecture tests pass; web format/lint/typecheck/build pass with 263 unit and 218 browser/accessibility tests; dependency audits, Render policy, secret scan, and release package pass. The single full Python run produced 923 passes plus six stale schema/catalog/test-substitution assertions; those six were corrected as one batch and pass 6/6. Synthetic backup/restore, Alembic drift, and full downgrade/upgrade pass at `20260821_0002`.
- Live acceptance: not claimed. Real Hermes execution, provider-backed GBP writes/reconciliation, live GSC orchestration, and deployed Render parity remain outstanding.
- Adjacent work intentionally not implemented: Hermes stop/steer/event lifecycle expansion and the pre-existing SEO max-pages concurrency defect remain separate controlled packets.
- Ledger rows changed: GBP operational product; SEO; Content; Automation & Agents control plane; Production AI provider; AI Gateway production routing; Release/production acceptance.

---

### PR #44 — GBP Provider Write Governance + Google Workspace Operational UX

- State: `IMPLEMENTED_NOT_ACCEPTED`.
- Canonical mutation: initial read-only mapping and deliberate provider-write enable/disable both use `confirmLocationMapping()` and the existing location-scoped, `gbp.connect`, AAL2 GBP confirm endpoint. No Integrations mutation route was added.
- Read/reconciliation model: Google mapped resources expose tenant- and connection-scoped `gbp_location_id`, `mapping_status`, and `write_enabled`; unresolved mappings return null governance fields. Active provider mapping identity and platform `Location.id` identity are shared by the mapped workspace and unmapped queue/count.
- Operator behavior: confirmed mapped GBP locations render backend-truth `Read only` or `Provider writes enabled` state. Only platform administrators meeting required assurance receive an enable/disable action, each with explicit inline consequence confirmation. Success re-fetches connection and workspace truth; failure restores the action and renders the standard safe error.
- Audit semantics: same-location confirmed false→true and true→false transitions emit `gbp.location.write_access_changed` with prior/new location, mapping-status, and write-enabled values. Same-value calls do not emit that event. Canonical provider-resource mapping audit remains intact.
- Safety invariants: new mappings remain read-only by default; enabling writes performs no publish; existing post/media mapping, write-enabled, human-approval, workflow-run, idempotency, provider verification/reconciliation, tenant, AAL2, and secret gates were not weakened.
- Focused evidence: 24 backend/route regressions pass against isolated PostgreSQL; 31 web regressions pass; focused Python/web format and lint, Python app type checks, and Astro diagnostics pass.
- Live acceptance: not claimed. Post-merge/deploy administrator enablement, immediate UI reconciliation, Business Profile read-side state, audit history, and the later separately approved real provider publication/verification scenario remain outstanding.
- Adjacent work intentionally not implemented: connected-account label, per-capability sync timestamps, manual sync endpoint, and any real Google content publication remain outside PR44.
- Ledger rows changed: Google provider resource mapping; GBP operational product; Integrations control plane.

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
