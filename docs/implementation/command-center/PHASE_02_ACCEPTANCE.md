# Command Center Phase 2 acceptance

State: `IMPLEMENTED_NOT_ACCEPTED` for live rollout. Repository implementation and deterministic acceptance are complete; exact gate results and environment limitations are recorded below. Live staging is `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`. No live provider acceptance is asserted.

## Repository state and reused implementation

Started on clean `command-center/phase-2` at Phase 1 merge `248fae154a5ed42c5ac68281ebb607511b985ef1`. Branch/status/last five commits were the only initial verification. Read AGENTS.md, CLAUDE.md, MASTER_PLAN, Phase 0 integration contract, acceptance matrix, Phase 0.5/1 acceptance, decision log and follow-on phases. Governing documents are present. Scope is only Integrations + Local Search; Phase 1 SSR/auth/BFF/generated-contract architecture remains authoritative.

Reused IntegrationDirectoryService, GBPConnectionService/OAuthIntentService, canonical Google discovery/mapping/sync routes, SearchConsoleService/AnalyticsService performance reports, SEOService crawl/page inventory, persisted Page Intelligence, GBPOperationsService exact post revisions/decisions/publications/recovery, ExecutionService/workflow registry/jobs, backend AuthorizationService and tenant-scoped ORM. No new provider abstraction, orchestration engine, database migration or provider configuration was introduced.

Evidence-backed gaps were console unavailable placeholders for these product areas; presentation fan-out without bounded read projections; missing atomic console crawl/publication dispatch contract; and OAuth return bound only to the existing web origin. Phase 0's absent geographic rank-grid/rank-scan and GBP performance sources remain absent.

## Implemented contracts

All paths below are under `/api/v1/organizations/{organization_id}` and use canonical UUID scope, authenticated principal before database handling, authoritative backend permissions and private/no-store responses.

| Added contract                                                                   | Authority and behavior                                                                                                                                                                                                                                                                                                                                      |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /command-center/integrations`                                               | Canonical Google connection/capabilities, reconnect/token verification, mappings/discovered GBP inventory, GSC/GA4 property mappings/freshness, bounded recent workflow state, permitted website/location choices and GitHub connection status. Provider inventory only in privileged Integrations. Source permissions evaluated independently.             |
| `GET /command-center/local-search?website_id=&days=7\|28\|90&offset=`            | Single projection over canonical GSC report, authorized GA4 report, bounded 50-page inventory with next offset, ten recent crawls, confirmed mapped/location-authorized GBP profiles and recent source sync state. No provider I/O during reads. GA4 remains explicitly organization-wide/all channels; never represented as selected-site organic traffic. |
| `GET /command-center/local-search/websites/{website_id}/pages/{page_id}`         | Persisted canonical Page Intelligence with scoped identity and independently governed source/evidence sections.                                                                                                                                                                                                                                             |
| `GET /command-center/local-search/locations/{location_id}/profiles/{profile_id}` | Requires canonical active mapping and confirmed scoped provider row. Snapshot, observed health, canonical completeness, exact revisions/publications and provider read-back; missing snapshot remains unavailable. LOCATION permissions/MFA and workflows.execute govern capabilities.                                                                      |
| `POST /seo/websites/{website_id}/check`                                          | Typed CrawlQueuedResponse; seo.manage + workflows.execute. Atomic canonical workflow and crawl/job enqueue using a website-bound idempotency key. No general workflow proxy.                                                                                                                                                                                |
| `POST /locations/{location_id}/gbp/operations/posts/{revision_id}/dispatch`      | Typed PostDispatchResponse; LOCATION gbp.publish AAL2 + workflows.execute. Atomic canonical workflow/reservation/job, exact approved revision, revision-bound idempotency and existing reconciliation. Queued is never published/verified.                                                                                                                  |
| Google connect optional `return_app: console`                                    | Existing clients default to web. Console requires bare HTTPS `LILOS_CONSOLE_ORIGIN`; console marker is included before hashing/persisting OAuth state. Callback returns only to this fixed origin after canonical state validation. No caller redirect URL or altered provider redirect registration.                                                       |

OpenAPI JSON and generated TypeScript transport contracts are regenerated. Typed UI adapters validate identities and preserve null/zero/quality/freshness. Closed BFF registers only these reads and explicit canonical discover/map/sync/connect/disconnect/profile/post/recovery actions, strict bodies and constrained queries. DELETE uses the existing CSRF/origin/host/permission boundaries. Browser modules bind before inert action controls activate; no automatic action replay.

## Production paths converted

- `/integrations/`: authorized client chooser and fixed OAuth organization resolver; scoped workspace Integrations uses canonical status, reconnect, explicit discovery/mapping, freshness and queued sync actions. GitHub publishing configuration remains in its existing control plane and Phase 4 scope.
- `/clients/{slug}/integrations/`: Google connection/capabilities, mapping/freshness and source errors replace the unavailable placeholder. Discovery never auto-confirms a resource. MFA remains backend enforced.
- `/clients/{slug}/local-search/`: Overview, Rankings, Google Business Profile, Search Console, Pages and Technical all render real projections or explicit unavailable states. Period/context, comparison, last sync and source quality remain visible. No fixture imports in production console.
- Local Search page and profile detail routes use scoped persisted Page Intelligence and confirmed GBP operations. Draft, exact approve/reject, dispatch and recovery use existing governed services; no direct provider writes.
- Presentation follows approved Command Center panels, tables, tabs and dialogs. Contrast correction is scoped to Phase 2 surfaces. Other product screens are preserved.

## Repository/synthetic acceptance

| Scenario                                                                                        | Result and evidence                                                                                                               |
| ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Empty/unmapped sources stay unavailable, no missing-to-zero conversion                          | PASS — adapter/unit, PostgreSQL projection and browser tests                                                                      |
| Real zero, missing comparison, stale source, partial quality and reconnect state                | PASS — persisted synthetic GSC report, typed adapter and both browser viewports                                                   |
| Cross-tenant, wrong website/page/location/profile and unauthenticated access                    | PASS — canonical API negatives, adapter identities, closed BFF and browser scoped URLs/cache                                      |
| Privileged discovery followed by explicit exact mapping and canonical sync                      | PASS — real HTTP synthetic upstream/browser; canonical mapping services retained                                                  |
| Crawl dispatch/workflow/job atomic idempotency and persisted page intelligence                  | PASS — disposable PostgreSQL with canonical workflow, mocked existing crawler boundary and one job on duplicate                   |
| GBP confirmed mapping required; snapshot absent explicit; AAL1 cannot approve/publish           | PASS — disposable PostgreSQL canonical mapping and authorization                                                                  |
| Post approval remains exact; unapproved dispatch denied; duplicate dispatch one reservation/job | PASS — existing GBP API integration suite extended; provider publication not inferred                                             |
| State-bound fixed OAuth console return, marker tampering rejected, old web flow intact          | PASS — canonical OAuth API test and settings validation negatives                                                                 |
| CSRF/origin/host/query/body allowlist/cache/fixture boundary                                    | PASS — console unit and existing security regression scenarios                                                                    |
| Tabs/page detail/profile draft, discovery/map/sync/crawl                                        | PASS — desktop/mobile browser synthetic journeys and axe; canonical PostgreSQL action tests separately establish backend behavior |

Synthetic browser upstream and fixtures live only under console tests. They are not provider or staging acceptance. Phase 0.5 factory/write-boundary tests remain in the full Python gate. No staging safety switch changed, no Google write performed.

## Tests actually run and final gates

Development: focused console units (39 passed), canonical SEO/profile tests (3 passed), GBP operations/OAuth tests (8 passed), configuration tests (26 passed), console typecheck and desktop/mobile Phase 2 journeys. Early new test assumptions about crawl status/range and frozen settings were corrected. Browser action readiness/navigation ordering and scoped contrast were corrected without weakening gates.

The integrated final gates ran once. Only Phase 2 corrections received focused follow-up checks; unrelated failures were classified once and not debugged broadly.

| Gate                                                            | Result                                                                                                                                                                                                                                                                                                                                                                                                                        |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run format:check`                                          | PASS — web/Python/console; final edited files additionally checked/formatted                                                                                                                                                                                                                                                                                                                                                  |
| `npm run lint`                                                  | PASS — web/Python/console and production fixture/session import boundaries; final edited components/tests checked                                                                                                                                                                                                                                                                                                             |
| `npm run typecheck`                                             | Initial FAIL in two new tests accessing ASGI app state; explicit FastAPI casts corrected. Focused Python mypy PASS (679 files), console Astro/TypeScript PASS (43 files, zero errors/warnings, four deprecated-navigation hints in new browser tests). Existing web PASS (182 files).                                                                                                                                         |
| `npm run test:web`                                              | PASS — 450 tests / 48 files                                                                                                                                                                                                                                                                                                                                                                                                   |
| `npm run test:console`                                          | PASS — 39 tests / five files; changed synthetic reporting-range fixture additionally passes six adapter/BFF tests                                                                                                                                                                                                                                                                                                             |
| `npm run build`                                                 | PASS — existing web and console SSR. Local Node 26 gives Vercel adapter Node 24 fallback warning; deployed console remains Node 22 / CI 22.22.3.                                                                                                                                                                                                                                                                              |
| `npm run check:console:browser`                                 | Initial 15 PASS / one mobile new-test timeout: offscreen sidebar sign-out. Test now opens existing mobile navigation; focused desktop/mobile two PASS. All 16 distinct scenarios PASS. Final comparison-range presentation separately verified in both Local Search viewports (two PASS), with axe unchanged.                                                                                                                 |
| `npm run check:browser`                                         | NOT EXECUTED after runner startup FAIL — existing listener on 127.0.0.1:4323 (PID 18795). No apps/web source/config changed; unrelated environment failure classified once, existing process not stopped. No existing-web browser acceptance claimed locally.                                                                                                                                                                 |
| `npm run contracts:check`                                       | PASS — deterministic byte drift/missing-artifact checks. Six new paths, no removed/changed existing paths; only existing schema change is optional GoogleConnectRequest return_app default web.                                                                                                                                                                                                                               |
| `npm run check:secrets`                                         | PASS                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `npm audit --audit-level=high` / `uv run pip-audit`             | PASS — no known vulnerabilities                                                                                                                                                                                                                                                                                                                                                                                               |
| Python shard inventory                                          | PASS — 218 files, complete union and zero overlap (55/55/54/54)                                                                                                                                                                                                                                                                                                                                                               |
| Full Python four shards                                         | Initial shards: 522 PASS; 449 PASS / three SKIP; 475 PASS; 426 PASS / one FAIL. The existing import test expects LOCAL but my harness set LILOS_ENV=test. No product fix: focused `LILOS_ENV=local .venv/bin/python -m pytest tests/python/test_api.py -q --tb=short` PASS (one test). All 1,873 distinct tests PASS / three SKIP after this environment correction; the original fourth shard exit remains recorded as FAIL. |
| `npm run check:release`                                         | PASS — structural repository acceptance package; not live rollout acceptance                                                                                                                                                                                                                                                                                                                                                  |
| `npm run check:render`                                          | PASS — both Blueprints and canonical validator; no deployment changes                                                                                                                                                                                                                                                                                                                                                         |
| `npm run check:production-preflight`                            | FAIL CLOSED — production environment/DB/release/Auth issuer/JWKS/telemetry configuration absent. Expected owner deployment configuration boundary, not a Phase 2 regression. Values not printed.                                                                                                                                                                                                                              |
| `npm run db:current`                                            | PASS — disposable local PostgreSQL head 20260930_0003                                                                                                                                                                                                                                                                                                                                                                         |
| Complete diff review / `git diff --check` and staged equivalent | PASS — 41 files, source/action/tenant/protection contracts reviewed; generated changes checked structurally and by regeneration                                                                                                                                                                                                                                                                                               |

Full Python tests use four distinct disposable local PostgreSQL 17 databases (`lilos_phase2_shard0_test` through `lilos_phase2_shard3_test`); no Supabase database or production credentials are used. Existing disposable `lilos_phase2_test` supports focused backend and db:current checks. No model/migration changed, so separate manual upgrade/check gate is not applicable (existing migration tests remain in full shards).

Tests not run: existing web browser scenarios due occupied port; live Supabase/Render/Vercel/OAuth/GitHub acceptance, real GBP publication/read-back, production canary and staging capacity/deployed security acceptance. These are not inferred from synthetic results. CI's clean environment must independently confirm the existing-web browser suite. The initial full-shard harness used LILOS_ENV=test; the repository-prescribed command sets only LILOS_TEST_DATABASE_URL and leaves the imported global app in its default local environment. Three existing onboarding reachability cases are skipped by their existing non-blocking-code conditions; no Phase 2 test is skipped.

## Live staging acceptance and owner checklist

Every live-only item is `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`. No live Supabase/Render/Vercel/OAuth/GitHub staging run, live Google read/write, deploy, production client mutation, canary or capacity measurement was performed.

- Confirm Phase 0.5 account access/costs, independent Supabase Auth/Postgres, backup/restore/telemetry and protected staging service/project setup.
- Supply separate staging API/worker/scheduler/Hermes and console server-only auth/encryption/CSRF/provider secrets, exact origin/API/host values, DNS/TLS/preview protection and Supabase redirects.
- Configure backend `LILOS_CONSOLE_ORIGIN=https://console-staging.lilosgrowth.com` (actual approved bare HTTPS console origin). Existing API Google callback URI remains unchanged. Verify actual OAuth state consumption and fixed console return under deployed settings.
- Run canonical staging seed/operator membership/product entitlements/location setup. Independently authorize Google, explicitly confirm real GSC/GA4 website properties and GBP location mapping; run refresh/read/sync/failure and cross-tenant/MFA acceptance. Retain staging Google write denial.
- Complete inherited Phase 1 protected-login, isolation, deployed cookie/host/CSRF, independent Google smoke, dedicated GitHub governed publication/PR/check/deploy/read-back and measured capacity scenarios. GitHub setup is the existing Phase 0.5 fixture/control plane, not a new Phase 2 publishing implementation.
- Capture deployed Phase 2 Integrations and all Local Search tab/page/profile read journeys, truthful freshness/partial/reconnect/error states, canonical crawl/sync and authorized safe synthetic post approval/recovery. Real GBP provider publication requires separate explicit approval and permitted environment; synthetic dispatch does not certify it.

## Explicit unsupported capabilities and adjacent work

Geographic rank grid/scan and rank-grid momentum/local visibility composites have no persisted canonical source/workflow. No scan action exists. GBP performance metrics are unavailable. Google confirmed indexation is unavailable; crawler indexability is labeled as crawler evidence. Technical health scores and prototype synthesized metrics are unavailable. Missing provider/profile/page/GA4 evidence stays unavailable. GA4 overview is organization/all channels; canonical page organic evidence is confined to Page Intelligence.

GitHub installation/publishing configuration stays in the existing control plane and Phase 4. Reviews, Website & Content, Leads, Automations, Reports, Portfolio and Administration migration remain in their assigned phases. No adjacent backend defect was broadened into this packet. No architecture/provider configuration changes.

## Exact release-ledger update and readiness

Appended only `Command Center Phase 2` to docs/PLATFORM-RELEASE-LEDGER.md: IMPLEMENTED_NOT_ACCEPTED for live rollout; projections/canonical actions/unsupported states, deterministic acceptance reference and owner live prerequisites. Decision log appends D40–D44. No prior acceptance state rewritten.

Phase 3 classification: `READY FOR PHASE 3 WITH LIVE STAGING ACCEPTANCE PENDING`, subject to Phase 2 review/merge, with the existing-web local browser environment limitation recorded above. Phase 3 has not begun. True blockers caused by Phase 2: none. External live staging prerequisites and the unrelated occupied existing-web browser port are carried forward separately.

## Exact files changed

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/integrations/connection_service.py`
- `apps/api/app/integrations/contracts.py`
- `apps/api/app/integrations/service.py`
- `apps/api/app/main.py`
- `apps/api/app/products/gbp/operations_contracts.py`
- `apps/api/app/products/seo/contracts.py`
- `apps/api/app/routes/command_center_search.py`
- `apps/api/app/routes/gbp_operations.py`
- `apps/api/app/routes/integrations.py`
- `apps/api/app/routes/seo.py`
- `apps/console/src/adapters/local-search.ts`
- `apps/console/src/components/integrations/Integrations.astro`
- `apps/console/src/components/local-search/LocalSearch.astro`
- `apps/console/src/components/local-search/PageIntelligence.astro`
- `apps/console/src/components/local-search/Performance.astro`
- `apps/console/src/components/local-search/Profile.astro`
- `apps/console/src/components/ui/DialogFrame.astro`
- `apps/console/src/layouts/AppLayout.astro`
- `apps/console/src/lib/search-actions.ts`
- `apps/console/src/pages/[...page].astro`
- `apps/console/src/pages/clients/[clientSlug]/[...workspace].astro`
- `apps/console/src/server/bff.ts`
- `apps/console/src/server/search-routes.ts`
- `apps/console/src/styles/app.css`
- `apps/console/tests/browser/phase2.spec.ts`
- `apps/console/tests/browser/upstream.mjs`
- `apps/console/tests/fixtures/phase2.json`
- `apps/console/tests/unit/local-search.test.ts`
- `apps/console/tests/unit/search-actions.test.ts`
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/implementation/command-center/DECISION_LOG.md`
- `docs/implementation/command-center/PHASE_02_ACCEPTANCE.md`
- `packages/contracts/openapi.json`
- `packages/contracts/src/generated/api.ts`
- `tests/python/api/test_config.py`
- `tests/python/gbp/test_command_center_profiles.py`
- `tests/python/gbp/test_gbp_operations_api.py`
- `tests/python/integrations/test_api.py`
- `tests/python/seo/test_command_center_search.py`
