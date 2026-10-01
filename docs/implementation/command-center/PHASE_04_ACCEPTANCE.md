# Phase 4 — Website & Content acceptance

State: `IMPLEMENTED_NOT_ACCEPTED` for live rollout.
Live staging: `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`.

## Repository state and canonical reuse

Started on clean `command-center/phase-4` at the requested stable Phase 3 head
`082a0fab012e7b23f719345d64a57b8d0a84e4ee`. Branch, status and five-commit log
were the only initial verification. All requested instructions and Command Center
handoffs were read; governing documents are present. Work is confined to the
independent `lilos-platform-phase4` worktree. The Phase 3 worktree was not modified.

Reused SEOService inventory/crawls, persisted Page Intelligence, canonical page-map
resolver and SiteChangeService, Phase 1 Opportunity detail/revise/exact decision,
ContentOperatorService/ContentService briefs/revisions/targets/publication/recovery,
ExecutionService workflow/jobs, authorization and existing GitHub publisher,
build/deployment/live verification handlers. No publishing engine, provider adapter,
model, migration, deployment/auth architecture or provider configuration added.

Evidence-backed gaps were the console Website & Content placeholder, missing bounded
composed read contracts, Content editor/actions and selected-site mapping linkage.
Named CTA event/path/funnel/friction observations remain absent; Content items have
organization scope rather than an authoritative website foreign key.

## Implemented contracts and journeys

Three additive typed reads under `/api/v1/organizations/{organization_id}/command-center/website-content`:

- Workspace: independently authorized SEO and Content sources, one selected UUID
  website, 50 pages/opportunities/content items with distinct next offsets, ten crawls,
  backend create/crawl capabilities and explicit unavailable conversion paths.
- `/websites/{website_id}/pages/{page_id}`: scoped canonical Page Intelligence,
  persisted page/repository/field-path mapping resolved by the canonical resolver,
  and exact page-linked opportunities. Configuration is not repository or live proof.
- `/content/{item_id}`: canonical operator detail, scoped grounding facts, immutable
  briefs/revisions, targets and frontmatter requirements, ten canonical AI draft runs,
  publications with exact revision/workflow/correlation/head/merge/build/deployment/
  verification evidence and canonical recovery eligibility. Reads perform no provider
  I/O; target reconciliation stays in the existing publish action.

Console SSR provides Overview, Pages, Content, Technical and Conversions plus page
and content dialogs. Page/site-change links reuse the complete Phase 1 governed path.
Content supports canonical item creation, grounded brief/new human revision, durable
AI draft, editorial/client exact revision decisions, target/assets selection,
idempotent publication dispatch and supported reconciliation recovery. No front-end
workflow state machine, provider write or automatic mutation replay exists.

Closed BFF permits only literal UUID reads and these existing canonical actions.
Strict bodies reject arbitrary repositories, workflow IDs and extra fields. Asset
reads accept only a UUID target. Server Bearer/correlation, input bounds, timeouts,
CSRF/session binding, Origin/host, backend permissions/AAL2 and private/no-store
responses remain intact. Production imports no test/reference fixtures.

Publication reserved/branch/PR/checks/merge/deployment/verified/failure/reconciliation
remain separate raw canonical states. Passing checks do not imply merge or deployment;
PR creation does not imply live success. Merge-ready is not a fabricated publication
state or a new manual merge control. Historical approved heads and external merge
revisions remain visible; unavailable live read-back stays unavailable.

## Repository/synthetic acceptance

| Scenario                                              | Result / evidence                                                                                                                                             |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Canonical page inventory and site/page linkage        | PASS: real canonical crawl/API projection; scoped adapters and desktop/mobile page journeys                                                                   |
| Missing/stale/partial evidence and technical findings | PASS: canonical inventory/quality preserved, adapter null/partial test, page evidence and Technical UI; no health/indexation inference                        |
| Site-change opportunity, revision and exact approval  | PASS: Phase 1 path reused; canonical executor/supersession/decision regressions; page/website links preserve source UUID                                      |
| Content brief/new revision/AI workflow                | PASS: real API scoped facts/brief/durable queued run; desktop/mobile immutable revision and new-item redirect                                                 |
| GitHub publication idempotency and target safety      | PASS: canonical API duplicate publication ID and existing operator/publisher/staging boundary regressions                                                     |
| PR/check/build/merge/deployment/live states           | PASS: all canonical publication states projected independently; browser PR/checks running with no deploy/live confirmation; existing live-proof handler tests |
| Failure/recovery and approved revision drift          | PASS: canonical lifecycle/executor regressions and backend recovery capability; terminal failed/checks-failed cannot be resumed through unsupported retry     |
| Conversion paths unavailable versus zero              | PASS: explicit no-source paths; adapter preserves sourced page keyEvents zero separately from missing/null evidence; no Leads totals fabricated               |
| Wrong tenant/site/page and unauthenticated            | PASS: canonical API negatives, adapter scope refusal, desktop/mobile BFF/SSR tests                                                                            |
| Closed BFF/body/query/CSRF/origin/host/cache          | PASS: five new adapter/BFF tests plus retained security tests; browser forgery/scoped UUID/private cache                                                      |
| No fixture authority                                  | PASS: production import-boundary script and negative boundary unit suite                                                                                      |
| Desktop/mobile and accessibility                      | PASS: six Phase 4 Playwright journeys with axe; screenshots captured for visual review                                                                        |

Synthetic HTTP browser tests exercise real console SSR/auth/MFA/BFF/UI with isolated
responses. Disposable PostgreSQL API tests separately prove canonical behavior.
Neither is live staging/provider acceptance.

## Validation actually run

Targeted development: two new API projection scenarios pass (including queued AI
workflow and publication state matrix); 69 existing canonical lifecycle/approval/
idempotency/recovery/live-verification/staging-write regressions pass; 31 focused
console adapter/BFF/security/boundary cases pass; six Phase 4 desktop/mobile browser
journeys pass. Changed-source Ruff/mypy/ESLint, console TypeScript and fixture-boundary
checks pass. PostgreSQL is disposable local `lilos_phase4_test` on port 55440.

Initial new tests incorrectly used a configuration export and an unlocated content
item with location-only facts; corrected test setup. Early browser failures identified
contrast, keyboard table focus/unique landmark labels and Astro formatter omissions;
corrected scoped source/components without weakening axe. Later added AI workflow
projection required canonical workflow-definition joins, and new test fixture types
were widened using the actual adapters. Focused affected checks passed afterward.

## Post-rebase final gates

Phase 3 PR #145 was confirmed merged at
`8db3ff4f1eef4f9d3fb421e18422bc521aa48ec5` on 2026-10-01. Phase 4 was committed,
fetched and rebased cleanly onto that actual `origin/main`. The reviewed candidate is
`2c0e0b3`; its diff contains only the 24 Phase 4 files below. No conflict resolution
or unrelated Phase 3 change was required. Full final gates ran once only after rebase.

| Gate                                                | Result                                                                                                                           |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `npm run format:check`                              | PASS                                                                                                                             |
| `npm run lint`                                      | PASS; fixture/session boundaries retained                                                                                        |
| `npm run typecheck`                                 | PASS; web/Python/console, four inherited deprecated-navigation hints                                                             |
| `npm run test:web`                                  | PASS — 450 tests / 48 files                                                                                                      |
| `npm run test:console`                              | PASS — 50 tests / seven files                                                                                                    |
| `npm run build`                                     | PASS — existing web and separate console SSR                                                                                     |
| `npm run check:console:browser`                     | PASS — 28 desktop/mobile journeys with axe                                                                                       |
| `npm run check:browser`                             | Runner startup FAIL — existing port 4323 listener; scenarios NOT RUN locally. Classified once; existing process not touched      |
| `npm run contracts:check`                           | PASS — byte drift; three additive paths/eleven schemas, zero changed or removed existing contracts                               |
| `npm run check:secrets`                             | PASS                                                                                                                             |
| `npm run check:release`                             | PASS — structural release package only                                                                                           |
| `npm run check:render`                              | PASS — both existing Blueprints unchanged                                                                                        |
| `npm run check:production-preflight`                | FAIL CLOSED — local environment, absent production DB/release/Auth issuer/JWKS/telemetry configuration; inherited owner boundary |
| `npm run db:current`                                | PASS — disposable local DB at 20260930_0003 head                                                                                 |
| `npm audit --audit-level=high` / `uv run pip-audit` | PASS — zero known vulnerabilities                                                                                                |
| Full Python four shards                             | FAIL — 1,878 PASS / three SKIP / one unchanged crawl regression FAIL; all new Phase 4 cases PASS, details below                  |
| `git diff --check` and full scope review            | PASS; final documentation-only evidence amendment also checked before commit                                                     |

Four independent disposable PostgreSQL 17 clusters on ports 55510–55513 each host
one `lilos_phase4_shardN_test` database, matching CI's independent-service isolation.
Inventory: 220 files, four sets of 55, complete union/zero overlap. No test DB is
Supabase or production. No migration/model changed. The clusters started for this
packet are stopped after their test runs; no existing cluster setting was changed.

Full Python shard results: shard 0, 429 PASS / one FAIL; shard 1, 438 PASS / three
SKIP; shard 2, 503 PASS; shard 3, 508 PASS. Existing Starlette deprecation warning
retained. Full Python acceptance is **not green**. No full-suite rerun.

Unrelated failure classified once:
`tests/python/seo/test_seo_api.py::test_crawl_survives_overlength_content_and_truncates_with_marker`
expects the overlong landing page at `https://example.test/` to be persisted after a
successful crawl; the row is absent. The test, SEOService and crawl engine are unchanged
against actual merged main. Root cause is unproven; no fix, test weakening or broad
debugging was performed. Clean CI must confirm this regression. All new Phase 4 API
cases and the focused 69 canonical lifecycle regressions passed. This failed existing
crawl check, the occupied old-web browser port and production configuration boundary
remain visible limitations; no all-gates PASS or live acceptance is claimed.

The initial unchanged Phase 3-head lockfile reported a high-severity `devalue`
advisory. Actual merged Phase 3 includes its canonical dependency fix (`06c4b8d`);
post-rebase reinstall and final audit report zero vulnerabilities. Phase 4 adds no
dependency change. Local Node 22.17.1 install warns about undici's newer patch engine;
deployment/CI pins remain unchanged and builds passed. No runtime/deployment claim
is inferred from local build success.

Desktop/mobile screenshots were visually inspected; the dialog is readable without
clipping or overlap. Live deployed auth/provider/GitHub/AI/read-back/capacity/canary
acceptance was not run. Existing-web browser acceptance requires a clean runner/CI;
no full-suite repeat or broad unrelated debugging was performed.

## Unsupported capabilities retained

Named CTA events, complete journeys/funnels/page-friction metrics, numeric page-health
scores and Google-confirmed indexation have no canonical source. Conversions renders
unavailable paths, not zero. Sourced page Organic Search landing evidence is available
through Page Intelligence with canonical period/quality/freshness; key events are not
measured business outcomes. Site-wide organic totals are not inferred by summing a
paginated inventory or substituting organization-wide all-channel metrics.

Content inventory is explicitly organization-scoped. Website selection never invents
content attribution. Missing/ambiguous target/page maps remain unavailable. Repository
current-value and approved-head drift checks remain canonical executor responsibilities.
Manual merge, invented merge-ready success, terminal publication retry, new templates,
asset upload and unsupported deployment verification are not invented.

## Live staging and owner actions

All live-only items remain `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`:

- Inherited independent Supabase Auth/Postgres, protected console/Vercel and four
  Render services, server-only secrets, exact hosts/origins, DNS/TLS/redirects,
  backup/restore/telemetry and capacity evidence from Phase 0.5–3.
- Canonical synthetic seed/operator membership/entitlements, independent Google
  read-only authorization/refresh and exact website mappings. Retain Google write denial.
- Dedicated permitted GitHub test repository/App installation/target/page map and
  allowed paths; actual deployed exact revision/approval/workflow/PR/check/merge/
  deployment/read-back evidence requires separate explicit write authorization.
- Deployed Website & Content desktop/mobile/page/editor/technical/conversion-source,
  AAL2, cross-tenant/cache/CSRF/error and reconciliation journeys; actual AI provider
  behavior and inherited measured capacity acceptance.
- Immutable UI baseline tag and later separately authorized qualified production
  canary remain inherited owner tasks. No real GitHub/client/provider mutation,
  staging provisioning, production SQL or live acceptance performed here.

## Ledger, adjacent work and readiness

Decision log appends D50–D54. Release ledger appends only Phase 4,
`IMPLEMENTED_NOT_ACCEPTED`, with this acceptance/owner checklist. Prior statuses unchanged.

Leads/business outcomes, Automations, Reports, Portfolio aggregates, Administration,
Settings/Onboarding and Phase 5 were intentionally not implemented. Missing conversion
instrumentation and Content website attribution are
recorded adjacent work; no parallel systems introduced.

Phase 5 readiness: repository scope implemented and post-rebase final gates executed;
review/clean CI confirmation of the recorded failures and Phase 4 merge are required
before Phase 5. Live staging remains pending. Do not merge this packet.

## Exact files changed

- `apps/api/app/main.py`
- `apps/api/app/routes/command_center_website.py`
- `apps/console/src/adapters/website-content.ts`
- `apps/console/src/components/website-content/ContentDetail.astro`
- `apps/console/src/components/website-content/PageDetail.astro`
- `apps/console/src/components/website-content/Publication.astro`
- `apps/console/src/components/website-content/Website.astro`
- `apps/console/src/layouts/AppLayout.astro`
- `apps/console/src/lib/content-actions.ts`
- `apps/console/src/pages/clients/[clientSlug]/[...workspace].astro`
- `apps/console/src/server/bff.ts`
- `apps/console/src/server/website-routes.ts`
- `apps/console/src/styles/app.css`
- `apps/console/tests/browser/phase4.spec.ts`
- `apps/console/tests/browser/upstream.mjs`
- `apps/console/tests/fixtures/phase4.json`
- `apps/console/tests/unit/website-content.test.ts`
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/implementation/command-center/DECISION_LOG.md`
- `docs/implementation/command-center/PHASE_04_ACCEPTANCE.md`
- `packages/contracts/openapi.json`
- `packages/contracts/src/generated/api.ts`
- `tests/python/content/test_command_center_website_content.py`
- `tests/python/seo/test_command_center_website.py`
