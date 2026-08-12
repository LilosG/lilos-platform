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
| Agency operating layer | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Dashboard renders KPIs + attention + work from real data; needs first-viewport convergence per Packet 4/6. Admin navigation role-aware (Packet 1). |
| Client workspace | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **Packet 1: Admin nav hidden for clients; unauthorized states on /administration, /onboarding.** Live client-role scoping still unverified without runtime access. |
| Entitlement-aware navigation | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | **Packet 1: Navigation role-aware via `_updateAdminNavigation()` checking platform admin status + membership type.** Backend authorization enforces per-request. |
| Unified onboarding | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | readiness partial | **Packet 2: Three-mode responsibility contract implemented.** `OnboardingOrchestrationService` extended with `managed`/`co_managed`/`self_service` modes over ONE engine. Co-managed step assignments persisted in `onboarding_step_assignments`. Client-facing onboarding API at `/api/v1/client/onboarding/`. Activation fail-closed in both agency and client paths. Frontend mode selector + co-managed assignment controls. Deterministic NULL→managed legacy contract. Auditor review pending. |
| Google connection lifecycle | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync partial | health partial | `GBPConnectionService` handles full OAuth lifecycle with incremental scopes. PR #10 repaired reconnect logic. Live acceptance: healthy connection must not re-prompt OAuth (unverified). |
| Google provider resource mapping | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | **Packet 1: Unmapped discovery removed from /gbp.** Mapping queue belongs in privileged Integrations workflow (Packet 3). API routes preserved. |
| GBP operational product | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync/media/post workflows partial | partial | **Packet 1: GBP API defaults to confirmed-only for gbp.read; frontend simplified.** Readiness engine uses integration_connected check for non-blocking LOCATION_PROFILE_MISSING. Provider writes fail-closed by default. **Deferred: list_accounts endpoint returns all accounts under gbp.read (accounts are parent entities, not locations).** |
| Reviews | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | ingestion/reply workflow partial | partial | Review models/services/routes fully implemented. `reviews.ingest` and `reviews.publish_response` handlers registered. Live evidence: 90 reviews reconciled/responded for Wheyland. |
| Search Console | IMPLEMENTED_NOT_ACCEPTED | unknown | IMPLEMENTED_NOT_ACCEPTED | sync unknown | partial | `SearchConsoleService` with discovery, mapping, sync. `SearchConsoleAdapter` for API calls. Live mapping/sync/freshness unverified. |
| GA4 | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync unknown | IMPLEMENTED_NOT_ACCEPTED | `AnalyticsService` with discovery, mapping, sync. Live metrics visible (Sessions 764, Users 576, Page Views 1201, Conversions 58). **Known gap: no period/comparison.** Insights page explicitly notes: "Current totals are shown without a period comparison because the reporting API does not yet return an observation window or comparable prior period." |
| SEO | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | SEO models/services/routes fully implemented. `seo.crawl_or_analysis` handler registered. Live crawl/GSC/recommendation lifecycle unverified. |
| Content | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Content models/services/routes fully implemented. `content.publish` handler registered. GitHub App installed for Wheyland. **Known blocker: 1 business fact needs confirmation through UI.** |
| Leads | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Lead models/services/routes fully implemented. `leads.send_communication` handler registered. **Status semantics gap: `sent` status may mean notification queued, not provider-dispatched.** `LeadCommunication` model has proper states (planned→queued→sent→delivered) but handler creates notification delivery records; actual provider dispatch delegated to notification delivery jobs. Live verification required. |
| Integrations control plane | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | health partial | Integration models/services/routes implemented. Integrations page exists. Needs central directory/detail/mapping convergence per Packet 3. |
| Automation & Agents control plane | IMPLEMENTED_NOT_ACCEPTED | n/a | NOT_STARTED | IMPLEMENTED_NOT_ACCEPTED | NOT_STARTED | 9 workflow handlers registered. Worker/scheduler runtime functional. **No evidence of active schedules in database.** Automation catalog/surface not yet productized. |
| Insights / reporting | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | scheduled reporting partial/unknown | IMPLEMENTED_NOT_ACCEPTED | **Packet 1: `gbp.locations` count now filters to `mapping_status == "confirmed"` only.** No period/comparison for GA4 metrics (Packet 6). Readiness contradictions resolved. |
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