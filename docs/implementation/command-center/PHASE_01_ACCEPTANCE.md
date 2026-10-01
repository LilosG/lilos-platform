# Phase 1 acceptance

Repository implementation: `IMPLEMENTED_NOT_ACCEPTED` for live rollout.
Readiness: `READY FOR PHASE 2 WITH LIVE STAGING ACCEPTANCE PENDING`. Repository gates below pass. No production or live provider acceptance is claimed.

## Inspected state and imported baseline

- Branch `command-center/phase-1`; starting HEAD `47f5744` (merged Phase 0.5/main).
- Initial branch, status and five-commit log verified. The only initial modification
  was the intentional replacement `PHASE_01_PROMPT.md`; preserved in this packet.
- Required Phase 1 integration documents and repository instructions inspected;
  governing documents present. Phase 0 inventory and Phase 0.5 design not repeated.
- Imported tracked UI source at exactly
  `d097c5255995b010f45b67a8ace90a80d00f090b` from
  `LilosG/lilos-command-center-astro`. No later source commit, `.git`, dependencies,
  build outputs or standalone deployment history imported. Baseline source/components
  are retained under `apps/console/reference/`; executable SSR adaptations are under
  `src/`. The approved styles, navigation hierarchy, panels and modal detail remain.
  The pointer-entry journey works in the imported console. Standalone baseline tests
  were not rerun or debugged. No missing tag blocked immutable SHA import.

## Implementation and canonical reuse

- Separate Astro SSR/Vercel workspace; old web scripts/CI/deployment remain intact.
  Console Node 22 requirement and CI 22.22.3 pin; local build runtime noted in gates.
  Phase 0.5 prerequisite validator runs for staging/preview builds; request-time
  validation enforces exact origin/API/Auth identity and deployment protection.
- Request-local Supabase SSR client; verified user before current Bearer use; Secure,
  HttpOnly, host-only session cookies in deployments, explicit local-only HTTP cookies.
  Password sign-in/local sign-out, bounded auth requests, MFA factor reuse/challenge/
  verification, unverified enrollment cleanup, safe return and chunk cleanup.
  Provider auth errors are redacted before SDK logging. No browser session material.
- All SDK cookie writes are buffered; failed stale refresh requests emit no session
  cookies, including deletes. Request-local cookie storage immediately reflects SDK
  writes. Two separate requests finish success/failure in both orders without clearing
  rotated cookies. A protected SSR failure performs one same-origin session recovery,
  then sign-in; uncertain mutations never automatically replay. Logout explicitly
  clears chunks; successful shrink retains SDK cleanup. No distributed lock invented.
- Fixed, closed method/path BFF registry; UUIDs, query keys/ranges and strict JSON
  mutation schemas; 16 KiB auth / 256 KiB BFF input, bounded response and timeouts;
  no redirect following, arbitrary upstream, cookie/hop-header forwarding or unsupported
  idempotency forwarding. Existing correlation flows into canonical actions/runs.
- Exact host/origin and HMAC session/actor-bound CSRF nonce; safe relative returns;
  private/no-store on SSR, BFF, error and redirect responses. No global tenant state.
- Canonical active organization slug resolves from authorized memberships once;
  downstream reads/actions use UUIDs. Unknown/foreign clients share not-found behavior.
- Additive read-only API projections use SEOService, canonical authorization, evidence
  resolution/quality gates, immutable recommendation revisions, implementation tasks,
  WorkflowRun and existing publication serializer. No new table, write model, workflow
  engine, provider orchestration or front-end quality/permission rules.
- Opportunity source IDs are `seo_opportunity:<uuid>`; classification follows structured
  SEO source types. This reference slice implements SEO Issue/Growth sources only.
  Optimization/Data & Tracking remain valid contract variants without invented records.
- Attention derives waiting approval, missing mapping, publication blocks, workflow
  failures/waiting/retry from those same canonical records. Its IDs include source and
  reason; there is no dismiss/resolve mutation or mirrored source count.
- Detail preserves source evidence, quality, observation period/freshness, page,
  priority, limitations, current/proposed values, rationale, protected signals,
  deterministic quality problems, revision status and hypothesis/effort. Backend
  quality is displayed, never recomputed in Astro. Current repository values and
  approved fingerprints are rechecked by the canonical executor; no live proof is
  inferred from an accepted request. Unsupported values remain unavailable.
- Edit calls the canonical revise route; approve/reject calls the exact revision's
  canonical decision route with backend AAL/action checks. Existing audited
  supersession, fingerprint, drift refusal, dispatch and reconciliation are preserved.
- Publication serializer adds canonical publication/run IDs, deployment status,
  approved head, external revision, published URL and verification timestamp while
  preserving existing web fields. Console shows PR/build/deploy/live observed checks
  and typed blockers. No direct GitHub/Vercel calls.
- Deterministic public OpenAPI export and pinned openapi-typescript output in the
  reserved contracts package; internal/tool endpoints excluded. CI regenerates in
  isolation and compares bytes, rejecting missing/stale artifacts. Tested adapters
  retain null/partial/unavailable states and reject source/tenant substitution.
- Production import-boundary gate excludes all prototype/sample-session/fixture
  authority. Isolated browser upstream simulation exists only in tests; production
  has no fixture mode or fallback. Future product screens retain explicit unavailable
  states; Phase 2 integrations/local-search work was not implemented.

## Repository / synthetic acceptance

| Scenario                                                  | Result / evidence                                                                                                  |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 1. Monorepo SSR console build                             | PASS — Final gate below                                                                                            |
| 2. Verified auth/session/expiry/recovery/logout           | PASS — Unit + real HTTP/browser SSR journey; final gate below                                                      |
| 3. MFA/AAL2, valid/invalid TOTP, cleanup and factor reuse | PASS — Browser journey plus canonical backend authorization regressions                                            |
| 4. BFF literal allowlist/security                         | PASS — Unit route/method/body/query/redirect/timeout/header negatives                                              |
| 5. CSRF/origin/host/returns                               | PASS — Unit negatives and browser forged mutation rejection                                                        |
| 6. Tenant/cache isolation                                 | PASS — Browser A warmed detail -> B same slug/source/BFF; private/no-store; backend foreign scope negatives        |
| 7. OpenAPI generation/drift                               | PASS — Deterministic repeated export, missing-artifact negative and byte drift gate                                |
| 8. Slug resolves once -> UUID                             | PASS — Authorized context loader and UUID-only SSR/BFF URLs                                                        |
| 9. Opportunity canonical source IDs                       | PASS — Projection API and adapter tests                                                                            |
| 10. Attention canonical operational states                | PASS — Projection/API, adapters and attention -> same detail browser test                                          |
| 11. Authoritative detail evidence                         | PASS — Backend persisted synthetic crawl and SSR browser detail                                                    |
| 12. Backend deterministic quality presentation            | PASS — Typed DTO quality plus canonical quality regression tests                                                   |
| 13. Revise -> new audited revision                        | PASS — Browser new revision; canonical backend revision/supersession tests                                         |
| 14. Exact revision approval                               | PASS — Browser exact URL/body; backend AAL, stale revision/fingerprint/current-value tests                         |
| 15. Durable workflow/run state                            | PASS — DTO canonical joins; browser state; canonical executor tests                                                |
| 16. Publication/PR/build/deploy/live state                | PASS — Additive serializer, browser provider-shaped synthetic result and canonical executor/live-proof regressions |
| 17. Fixture imports blocked                               | PASS — Production boundary scan and four negative import/browser-authority cases                                   |
| 18. Unauthorized/cross-tenant actions rejected            | PASS — Canonical backend scope/AAL tests and browser/BFF negatives                                                 |
| 19. Existing web intact                                   | PASS — Existing web unit/build gates; no old web source or deployment changes                                      |

Browser simulation proves the real console SSR/auth/CSRF/BFF/UI path using isolated
HTTP responses. Canonical backend tests separately prove audited revise/approval/
executor behavior with disposable PostgreSQL and existing provider seams. Phase 0.5
provider contract/write-isolation checks are included in the affected backend gate.
Neither synthetic HTTP nor existing fixtures certify a live Google/GitHub deployment.

## Final gates

The required final gates ran once; only Phase 1 failures were corrected with focused
checks afterward. Results:

| Gate                                                 | Result                                                                                                                                                                  |
| ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run format:check`                               | PASS: existing web, Python, console; changed files formatted after corrections                                                                                          |
| `npm run lint`                                       | Existing web PASS; one new Python import ordering failure corrected with focused Ruff; console PASS after excluding generated `.vercel` output                          |
| `npm run typecheck`                                  | PASS: existing web, Python, console Astro/TypeScript; corrected detail rechecked with console typecheck                                                                 |
| `npm run test:web`                                   | PASS: 450 tests / 48 files                                                                                                                                              |
| `npm run test:console`                               | PASS: 32 tests / 3 files, including fixture-boundary negatives                                                                                                          |
| Affected backend pytest (listed below)               | PASS: 118 tests, disposable PostgreSQL 17; one existing Starlette deprecation warning                                                                                   |
| `npm run build`                                      | PASS: existing web and separate console SSR; corrected detail rebuilt with `npm run build:console`                                                                                                                             |
| `npm run check:console:browser`                      | Initial 6 PASS / 4 FAIL; corrected detail summary omission and isolated synthetic race tokens; focused rerun 6 PASS, both viewports. All 10 distinct scenarios now PASS |
| Axe / auth / MFA / CSRF / tenancy / refresh ordering | PASS in applicable desktop/mobile browser and unit cases                                                                                                                |
| `npm run contracts:check`                            | PASS: isolated byte comparison, deterministic export and missing-artifact negative                                                                                      |
| `npm run check:secrets`                              | PASS                                                                                                                                                                    |
| `npm audit --audit-level=high`                       | PASS: zero vulnerabilities                                                                                                                                              |
| `git diff --check`                                   | PASS                                                                                                                                                                    |

Affected backend command (with isolated test DB environment):

```sh
.venv/bin/python -m pytest tests/python/seo/test_command_center.py tests/python/api/test_console_contracts.py tests/python/seo/test_change_quality.py tests/python/seo/test_site_change_operator_state.py tests/python/seo/test_hermes_change_set.py tests/python/seo/test_site_change_executor.py tests/python/seo/test_revision_supersession.py tests/python/seo/test_governed_decision.py tests/python/seo/test_live_verification.py tests/python/staging/test_provider_contracts.py tests/python/staging/test_write_boundary.py -q --tb=short
```

Corrected browser command:

```sh
npm run browser:test --workspace @lilos/console -- --grep 'SSR login|distributed stale'
```

One attempted focused rerun forwarded arguments incorrectly and selected no tests;
it is not counted as acceptance. The correct command above passed all six selected
cases. Console lint after build excludes generated deployment output, preserving
all source rules. Backend import correction passed focused Ruff/format checks.
Local Node 26 produced the adapter's Node 24 fallback warning; console's Node 22
engine and CI's 22.22.3 pin govern deployed builds. No deployment runtime acceptance
is inferred from this local build. Complete diff reviewed; all 143 retained reference
files verified byte-for-byte against the approved SHA, generated contracts verified
by regeneration, and no build outputs/dependency directories are staged.

Development checks were focused:
28 initial unit tests, projection/contract checks, desktop reference/MFA/axe, adversarial
refresh ordering, changed-file static checks and console SSR build. Initial development
failures in new loader/test configuration were corrected. The evidence-panel contrast
failure (4.37:1) was fixed locally without weakening axe. No unrelated failures debugged.

PR #143 CI correction: Command Center now requires the canonical authenticated
principal at router level before database processing, retaining no-store and policies.
The Python drift negative test mocks generator output and covers missing/changed
schema and type artifacts; dedicated console CI retains the real byte-for-byte
generator check. Targeted auth-order, authentication API, Command Center and contract
tests passed (12 tests); changed-file Ruff/format and `git diff --check` passed.

No schema/migration or Python dependency changed. Full repository Python shards,
production preflight/release/live provider/canary and staging performance checks are
not run locally for this phase. CI retains its broader original gates. No live assets,
production database, client repository or production credentials used.

## Live staging acceptance and consolidated owner actions

All eight live staging scenarios are
`PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`:
protected login, Supabase Auth/Postgres isolation, synthetic org access, independent
Google smoke, dedicated GitHub publication, real PR/check/deploy/read-back, deployed
cookie/host/protection behavior and measured performance.

One consolidated checklist (Phase 0.5 setup contract remains authoritative):

- Approve costs and confirm Render/Supabase/Vercel access, actual regions, protection
  entitlement, restore/backup evidence and telemetry.
- Provision separate staging Supabase Auth/Postgres and independent protected DB,
  Auth, encryption/CSRF/OAuth/App/Hermes/inference secrets and production fingerprints.
  Supply console server-only key/CSRF secret, exact origin/API/project/host values.
- Provision the four staging services and protected separate Vercel console project;
  configure DNS/TLS, exact trusted preview hosts and Auth redirect settings.
- Run canonical staging seed and operator membership/entitlement/onboarding setup.
- Connect the actual dedicated GitHub test repo/App/target/page map/allowed paths;
  enable scoped staging writes and capture real governed publication evidence.
- Independently authorize staging Google GSC/GA4 reads, confirm GBP scope, configure
  explicit smoke org/mappings/schedules and capture refresh/read/failure evidence.
- Run the eight live acceptance scenarios, including performance and deployed cookie
  behavior, before production rollout. Baseline tag publication remains a durable
  reference owner task; no canary is run or ordinary business page changed here.

No paid resource provisioned. No true Phase 1 architecture/external implementation
blocker. Phase 2 may begin after review/merge with live staging acceptance pending;
this packet stops at its PR. Adjacent portfolio aggregates, other source families,
provider setup, product tabs, reports/admin and performance acceptance are reserved
for their existing later phases; no unrelated cleanup or product work performed.

## Exact files changed

This packet changes 205 files, including 143 immutable imported reference
files, generated transport artifacts and the intentional replacement prompt.

```text
.github/workflows/ci.yml
.gitignore
apps/api/app/main.py
apps/api/app/products/seo/site_change_state.py
apps/api/app/routes/command_center.py
apps/console/.env.example
apps/console/.prettierignore
apps/console/README.md
apps/console/astro.config.mjs
apps/console/eslint.config.mjs
apps/console/package.json
apps/console/playwright.config.ts
apps/console/prettier.config.mjs
apps/console/reference/.gitignore
apps/console/reference/.prettierrc.json
apps/console/reference/astro.config.mjs
apps/console/reference/eslint.config.mjs
apps/console/reference/package.json
apps/console/reference/playwright.config.ts
apps/console/reference/src/components/app/ActivityItem.astro
apps/console/reference/src/components/app/AttentionDialog.astro
apps/console/reference/src/components/app/AttentionItem.astro
apps/console/reference/src/components/app/AttentionList.astro
apps/console/reference/src/components/app/Dialogs.astro
apps/console/reference/src/components/app/Sidebar.astro
apps/console/reference/src/components/app/TopBar.astro
apps/console/reference/src/components/app/UpcomingWork.astro
apps/console/reference/src/components/automations/Automations.astro
apps/console/reference/src/components/automations/Filters.astro
apps/console/reference/src/components/automations/Inventory.astro
apps/console/reference/src/components/automations/RunDialog.astro
apps/console/reference/src/components/client/GrowthOverview.astro
apps/console/reference/src/components/client/Overview.astro
apps/console/reference/src/components/client/PerformanceInsight.astro
apps/console/reference/src/components/client/PerformanceSnapshot.astro
apps/console/reference/src/components/client/Settings.astro
apps/console/reference/src/components/integrations/ClientIntegrations.astro
apps/console/reference/src/components/integrations/ConnectionDialog.astro
apps/console/reference/src/components/integrations/ConnectionsDialog.astro
apps/console/reference/src/components/integrations/PortfolioIntegrations.astro
apps/console/reference/src/components/leads/EventDialog.astro
apps/console/reference/src/components/leads/LeadDialog.astro
apps/console/reference/src/components/leads/Leads.astro
apps/console/reference/src/components/leads/Outcomes.astro
apps/console/reference/src/components/local-search/LocalSearch.astro
apps/console/reference/src/components/local-search/MomentumPanel.astro
apps/console/reference/src/components/local-search/PostDialog.astro
apps/console/reference/src/components/local-search/ProfileDialog.astro
apps/console/reference/src/components/local-search/QueryTable.astro
apps/console/reference/src/components/local-search/RankingDistribution.astro
apps/console/reference/src/components/local-search/RankingRows.astro
apps/console/reference/src/components/local-search/SearchPerformance.astro
apps/console/reference/src/components/local-search/VisibilityChart.astro
apps/console/reference/src/components/navigation/ClientNav.astro
apps/console/reference/src/components/navigation/PortfolioNav.astro
apps/console/reference/src/components/navigation/TabNav.astro
apps/console/reference/src/components/opportunities/Findings.astro
apps/console/reference/src/components/opportunities/Opportunities.astro
apps/console/reference/src/components/opportunities/OpportunityDetail.astro
apps/console/reference/src/components/opportunities/OpportunityList.astro
apps/console/reference/src/components/opportunities/OpportunityRow.astro
apps/console/reference/src/components/portfolio/Activity.astro
apps/console/reference/src/components/portfolio/Administration.astro
apps/console/reference/src/components/portfolio/Attention.astro
apps/console/reference/src/components/portfolio/ClientRows.astro
apps/console/reference/src/components/portfolio/ClientTable.astro
apps/console/reference/src/components/portfolio/Dashboard.astro
apps/console/reference/src/components/reports/ClientReport.astro
apps/console/reference/src/components/reports/HistoricalPerformanceDialog.astro
apps/console/reference/src/components/reports/HistoryDialog.astro
apps/console/reference/src/components/reports/MonthlyPerformanceDialog.astro
apps/console/reference/src/components/reports/ReportDialog.astro
apps/console/reference/src/components/reports/Reports.astro
apps/console/reference/src/components/reviews/RequestDialog.astro
apps/console/reference/src/components/reviews/ResponseDialog.astro
apps/console/reference/src/components/reviews/ReviewOpportunities.astro
apps/console/reference/src/components/reviews/ReviewRequests.astro
apps/console/reference/src/components/reviews/Reviews.astro
apps/console/reference/src/components/ui/DataTable.astro
apps/console/reference/src/components/ui/DateControl.astro
apps/console/reference/src/components/ui/DialogFrame.astro
apps/console/reference/src/components/ui/EmptyState.astro
apps/console/reference/src/components/ui/ErrorState.astro
apps/console/reference/src/components/ui/FilterBar.astro
apps/console/reference/src/components/ui/InsightPanel.astro
apps/console/reference/src/components/ui/MetricItem.astro
apps/console/reference/src/components/ui/MetricStrip.astro
apps/console/reference/src/components/ui/MetricValue.astro
apps/console/reference/src/components/ui/PageHeader.astro
apps/console/reference/src/components/ui/PeriodTotal.astro
apps/console/reference/src/components/ui/PeriodValue.astro
apps/console/reference/src/components/ui/SectionHeading.astro
apps/console/reference/src/components/ui/StatusBadge.astro
apps/console/reference/src/components/ui/Trend.astro
apps/console/reference/src/components/website-content/ContentDialog.astro
apps/console/reference/src/components/website-content/ContentOperations.astro
apps/console/reference/src/components/website-content/ConversionPaths.astro
apps/console/reference/src/components/website-content/Conversions.astro
apps/console/reference/src/components/website-content/LandingPageDialog.astro
apps/console/reference/src/components/website-content/LandingPages.astro
apps/console/reference/src/components/website-content/PageDialog.astro
apps/console/reference/src/components/website-content/PageTable.astro
apps/console/reference/src/components/website-content/Technical.astro
apps/console/reference/src/components/website-content/TechnicalFindings.astro
apps/console/reference/src/components/website-content/Website.astro
apps/console/reference/src/config/routes.ts
apps/console/reference/src/data/fixtures/actions.ts
apps/console/reference/src/data/fixtures/activity.ts
apps/console/reference/src/data/fixtures/administration.ts
apps/console/reference/src/data/fixtures/automationDefs.ts
apps/console/reference/src/data/fixtures/automationRuns.ts
apps/console/reference/src/data/fixtures/clientPerformance.ts
apps/console/reference/src/data/fixtures/clients.ts
apps/console/reference/src/data/fixtures/conversionEvents.ts
apps/console/reference/src/data/fixtures/growthWorkspaces.ts
apps/console/reference/src/data/fixtures/hospitalitySearchQueries.ts
apps/console/reference/src/data/fixtures/index.ts
apps/console/reference/src/data/fixtures/insights.ts
apps/console/reference/src/data/fixtures/leads.ts
apps/console/reference/src/data/fixtures/measurements.ts
apps/console/reference/src/data/fixtures/metrics.ts
apps/console/reference/src/data/fixtures/opportunities.ts
apps/console/reference/src/data/fixtures/pageRecords.ts
apps/console/reference/src/data/fixtures/pageSignals.ts
apps/console/reference/src/data/fixtures/presentation.ts
apps/console/reference/src/data/fixtures/rankingDistribution.ts
apps/console/reference/src/data/fixtures/reportHistory.ts
apps/console/reference/src/data/fixtures/reports.ts
apps/console/reference/src/data/fixtures/reviewRecords.ts
apps/console/reference/src/data/fixtures/snapshots.ts
apps/console/reference/src/data/fixtures/systems.ts
apps/console/reference/src/layouts/AppLayout.astro
apps/console/reference/src/lib/dialogs.ts
apps/console/reference/src/lib/filters.ts
apps/console/reference/src/lib/interactions.ts
apps/console/reference/src/lib/model-context.ts
apps/console/reference/src/lib/record-views.ts
apps/console/reference/src/lib/sample-session.ts
apps/console/reference/src/lib/selectors.ts
apps/console/reference/src/lib/status.ts
apps/console/reference/src/lib/view.ts
apps/console/reference/src/lib/visibility.ts
apps/console/reference/src/lib/workflows.ts
apps/console/reference/src/lib/workspace-data.ts
apps/console/reference/src/pages/[...page].astro
apps/console/reference/src/pages/clients/[clientSlug]/[...workspace].astro
apps/console/reference/src/styles/app.css
apps/console/reference/src/styles/theme.css
apps/console/reference/src/types/domain.ts
apps/console/reference/tests/browser/navigation.spec.ts
apps/console/reference/tests/browser/parity.spec.ts
apps/console/reference/tests/browser/reference-coverage.spec.ts
apps/console/reference/tests/browser/workflows.spec.ts
apps/console/reference/tests/unit/domain.test.ts
apps/console/reference/tsconfig.json
apps/console/reference/vitest.config.ts
apps/console/scripts/check-boundaries.mjs
apps/console/src/adapters/opportunities.ts
apps/console/src/components/opportunities/OpportunityDetail.astro
apps/console/src/components/opportunities/OpportunityRow.astro
apps/console/src/components/ui/DataTable.astro
apps/console/src/components/ui/DialogFrame.astro
apps/console/src/components/ui/EmptyState.astro
apps/console/src/components/ui/FilterBar.astro
apps/console/src/components/ui/InsightPanel.astro
apps/console/src/components/ui/SectionHeading.astro
apps/console/src/components/ui/Trend.astro
apps/console/src/env.d.ts
apps/console/src/layouts/AppLayout.astro
apps/console/src/middleware.ts
apps/console/src/pages/[...page].astro
apps/console/src/pages/api/[...path].ts
apps/console/src/pages/auth/[action].ts
apps/console/src/pages/clients/[clientSlug]/[...workspace].astro
apps/console/src/pages/login.astro
apps/console/src/pages/mfa.astro
apps/console/src/server/bff.ts
apps/console/src/server/config.ts
apps/console/src/server/context.ts
apps/console/src/server/security.ts
apps/console/src/server/session.ts
apps/console/src/styles/app.css
apps/console/src/styles/theme.css
apps/console/tests/browser/reference-slice.spec.ts
apps/console/tests/browser/upstream.mjs
apps/console/tests/unit/adapters.test.ts
apps/console/tests/unit/boundaries.test.ts
apps/console/tests/unit/security.test.ts
apps/console/tsconfig.json
apps/console/vercel.json
apps/console/vitest.config.ts
docs/PLATFORM-RELEASE-LEDGER.md
docs/implementation/command-center/DECISION_LOG.md
docs/implementation/command-center/PHASE_01_ACCEPTANCE.md
docs/implementation/command-center/PHASE_01_PROMPT.md
package-lock.json
package.json
packages/contracts/README.md
packages/contracts/openapi.json
packages/contracts/package.json
packages/contracts/src/generated/api.ts
scripts/check_contracts.py
scripts/export_openapi.py
tests/python/api/test_console_contracts.py
tests/python/seo/test_command_center.py
```
