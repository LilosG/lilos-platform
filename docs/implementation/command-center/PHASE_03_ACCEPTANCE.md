# Phase 3 — Reviews acceptance

Repository implementation: `IMPLEMENTED_NOT_ACCEPTED` for live rollout.
Starting branch: `command-center/phase-3`; clean HEAD
`3b5b3b31d52f23ea6e83eaaa8a646af2db05bca8` (merged Phase 2).
Only branch/status/five-commit log were inspected before the required documents.
All requested Command Center documents and repository instructions were read;
governing documents exist. Reviews-only code inspection followed; Phase 0 discovery
and Phase 0.5 environment design were not repeated.

## Implementation and contracts

- `GET /api/v1/organizations/{organization_id}/command-center/reviews` accepts
  optional UUID `location_id` and bounded `offset`. It returns only locations with
  canonical `reviews.read` authorization, one selected location's paginated inventory,
  persisted inventory count/average rating/open restricted cases, canonical Google
  connection/mapping status and review-import freshness. Empty inventory without
  import evidence yields null counts; completed empty import supports true zero.
  Quality remains partial: persisted inventory is not a provider-wide coverage claim.
- `GET .../reviews/locations/{location_id}/{review_id}` returns current review
  revision/source identity, scoped approved grounding facts, exact response revisions,
  action capabilities, canonical workflow status/failure, approval/publish timestamps,
  provider references/error codes and permission-gated canonical audit histories.
  Missing author/source/time/metrics remain explicit; no fixture fallback.
- The two generated OpenAPI response contracts are `ReviewsWorkspace` and
  `ReviewDetail`, with typed nested source, revision, response, fact and history DTOs.
  Console adapters validate UUID scope and preserve states before presentation.
- Closed BFF permits only these reads plus existing canonical Reviews ingestion,
  manual draft, AI draft, exact revision approval and publication reservation.
  UUID paths/query, strict bodies, approved-fact references, bounded inputs, server
  Bearer, CSRF/origin/host protections and private/no-store responses are preserved.
  No generic workflow dispatch, provider proxy or manual retry route is exposed.
- Production `/clients/{slug}/reviews/`, `/reviews/requests/` and
  `/reviews/locations/{location UUID}/{review UUID}/` now present the approved inbox,
  metric strip and response dialog using authoritative data or explicit unavailable
  states. Location selection and pagination preserve UUID scope. Approved shell,
  SSR/Supabase auth, MFA and prior product slices remain intact.
- Drafting uses the existing `ReviewService` and AI Gateway only. Approved facts are
  selected from scoped canonical records; manual drafting now validates those
  references through the existing governed-fact resolver and refuses stale review
  revisions. Saving creates a new response revision; existing revisions are not edited.
- Publication still uses `ReviewService.reserve_publication`, `ExecutionService`,
  the existing job worker, GBP provider adapter and write-once/read-back handler.
  Exact duplicate reservation returns the existing state without re-enqueue/audit;
  review revision is rechecked before initial reservation. No provider-write boundary
  or staging write-denial configuration changed.
- Audit/history reuses canonical immutable events. Workflow queued/running/retry/failure
  and response publishing/published/reconciliation-required are separate fields.
  Provider reference alone is not confirmation. Canonical worker retry/read-back and
  existing ingestion reconciliation remain the recovery mechanisms.

## Approval policy evidence

Current merged `ReviewService.draft` creates `awaiting_approval`; reservation requires
`approved`, and approval/publish routes require their separate permissions and AAL2.
No canonical client/location approval-free local response policy exists. The console
reports `canonical_local_response_approval` from the backend for each local response;
it does not derive policy from rating, role, industry or prototype preferences.
Restricted/escalated reviews retain the existing publication denial even after approval.

Provider-imported replies are canonical observations, require **no local approval**,
and can be published/provider-observed with null approval fields and no local workflow.
The backend reports `provider_observation_no_local_approval` for those records. This
is not authorization for automatic local publishing. Client/industry policy overrides
remain explicitly unavailable until a canonical rule exists; no blanket frontend
approval gate or second policy system was introduced.

## Repository / synthetic acceptance

Acceptance uses the real console SSR/auth/BFF/UI against isolated HTTP test fixtures,
and the real canonical backend against disposable local PostgreSQL. These are separate
proofs, neither of which certifies live providers.

| Scenario                                                      | Evidence / result                                                                                                                                                                           |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Empty inventory, true zero versus missing metrics             | API projection tests and adapter null/zero cases; average remains null for empty inventory                                                                                                  |
| Stale/partial/reconnect/unmapped/unavailable/provider failure | Source projection, typed adapter cases, browser health and existing canonical ingestion/handler failure regressions                                                                         |
| Tenant/location/auth/AAL2 isolation                           | API negatives, existing Reviews authorization suite, BFF and desktop/mobile tests                                                                                                           |
| Required approval and restricted-review denial                | Existing canonical service/API tests plus exact policy/capability projection tests                                                                                                          |
| No local approval for provider observations                   | New API projection test plus existing ingestion tests; no unsupported approval-free local policy claimed                                                                                    |
| Manual/new revision/AI drafting                               | Canonical API tests and exact-body browser draft journey; approved fact grounding and stale revision checks                                                                                 |
| Unapproved publish denial, idempotent dispatch                | API tests: denial before approval; duplicate reservation retains one canonical dispatch and audit event                                                                                     |
| Queued versus published/reconciled/read-back                  | Browser MFA approval/dispatch remains publishing/queued/unconfirmed; canonical provider handler/ingestion tests cover confirmed, pending, ambiguous, mismatch, rejected and removed replies |
| Failed/retry/recovery and audit integrity                     | Existing write-once handler and in-flight ingestion tests; projected workflow/error/history and no manual retry endpoint                                                                    |
| Closed BFF/body/query/CSRF/origin/host/cache/fixtures         | New Reviews allowlist tests plus retained foundation security and boundary suites                                                                                                           |
| Desktop/mobile and accessibility                              | Reviews inbox, unavailable campaigns, exact draft/audit, MFA approval/queued dispatch and axe in both viewports                                                                             |

PASS for all listed Reviews repository/synthetic scenarios after the focused corrections recorded below. Live staging scenarios remain pending.

## Final gates and tests actually run

The broad final gates ran once; only Phase 3 corrections received focused follow-up.

PR #145 CI dependency correction: its sole reported failure was the high-severity
`devalue <=5.9.2` audit finding. Updated only the transitive lockfile entry from
5.9.2 to 5.9.4 within Astro 7.3.2's existing `^5.8.1` range; no manifest or
application changes. Follow-up `npm audit --audit-level=high` PASS (zero
vulnerabilities), `npm run build:console` PASS, and `npm run test:console` PASS
(45 tests across six files). Broader gates were not rerun for this correction.

| Gate                                                  | Result                                                                                                                                                                                                                                                                                                        |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run format:check`                                | PASS; final amended source/docs additionally formatted and checked                                                                                                                                                                                                                                            |
| `npm run lint`                                        | PASS; final error helper, form and test additionally pass focused ESLint                                                                                                                                                                                                                                      |
| `npm run typecheck`                                   | PASS — existing web, Python (680 files), console; final amendments additionally pass console TypeScript                                                                                                                                                                                                       |
| `npm run test:web`                                    | PASS — 450 tests / 48 files                                                                                                                                                                                                                                                                                   |
| `npm run test:console`                                | Initial 44 PASS / one new test FAIL: happy-dom Request implementation in a BFF test. Use Node for BFF and guard browser initialization during pure helper import. Focused final Reviews suite six PASS; all 45 distinct console cases pass after correction. Original full-run exit remains recorded as FAIL. |
| `npm run build`                                       | PASS — existing web and console SSR; final explicit form label additionally passes console rebuild. Local Node 26 produces existing Vercel Node 24 fallback warning; deployment Node 22/CI pin unchanged.                                                                                                     |
| `npm run check:console:browser`                       | Initial 20 PASS / two new viewport FAIL: implicit textarea label included prefilled text in the label selector. Corrected explicit label; both affected inbox/draft/history journeys PASS with axe. All 22 distinct console scenarios pass after focused corrections. Original full-run exit remains FAIL.    |
| `npm run check:browser`                               | Runner startup FAIL — existing listener at 127.0.0.1:4323, same limitation recorded by Phase 2. Existing process not stopped; no apps/web source/config changes. Scenarios NOT RUN locally.                                                                                                                   |
| `npm run contracts:check`                             | PASS — deterministic byte drift; exactly two added paths/eight new schemas, zero removed/changed existing paths or schemas                                                                                                                                                                                    |
| `npm run check:secrets`                               | PASS                                                                                                                                                                                                                                                                                                          |
| `npm audit --audit-level=high` and `uv run pip-audit` | PASS — no known vulnerabilities                                                                                                                                                                                                                                                                               |
| Python four-shard inventory                           | PASS — 218 files, complete union, zero overlap                                                                                                                                                                                                                                                                |
| Full Python four shards                               | FAIL — shard 0: 521 PASS / one setup ERROR; shard 1: 452 PASS / three SKIP / one setup ERROR; shard 2: 474 PASS / one setup ERROR; shard 3: 426 PASS / one setup ERROR. Total 1,873 PASS / three SKIP / four setup ERROR; all 38 Reviews cases PASS. No broad rerun.                                          |
| `npm run check:release`                               | PASS — structural release gate, not live acceptance                                                                                                                                                                                                                                                           |
| `npm run check:production-preflight`                  | FAIL CLOSED — local environment and absent production DB/release/Auth issuer/JWKS/telemetry configuration; inherited owner boundary, no Phase 3 deployment changes                                                                                                                                            |
| `npm run db:current`                                  | PASS — disposable local database at 20260930_0003 head                                                                                                                                                                                                                                                        |
| Complete diff review / `git diff --check`             | PASS after complete source/test review and generated contract structural/byte checks; final staged check recorded at commit                                                                                                                                                                                   |

Focused development/acceptance: original Reviews domain suite 35 PASS/two FAIL;
canonical review supersession expectation and fabricated fact fixture corrected.
API/ingestion focused rerun 25 PASS; final API projection/policy suite nine PASS,
including the added provider-observed no-approval scenario. Six focused Reviews
browser scenarios passed before final gates; final corrected two viewport journeys
also passed. Initial CSRF test argument order, Node JSON import attribute and Astro
whitespace assertions were corrected during development. No gate was weakened.

`agent-browser` CLI was unavailable; repository Playwright/axe performed the real
browser verification. Desktop/mobile screenshots were visually inspected. No
model/migration/dependency/environment/hosting changes. Python tests use only local
`lilos_phase3_test` and four `lilos_phase3_shardN_test` databases on PostgreSQL 17;
no Supabase or production database was used.

Full Python setup-error classification (once, no broad debugging): unchanged
Administration reconciliation/effective-fact, Business Identity service and
Authentication API fixtures fail during Alembic downgrade of existing constraints
with `asyncpg.exceptions.OutOfMemoryError: out of shared memory`, hinting
`max_locks_per_transaction`. Local test cluster setting confirmed as 64. Four isolated
databases share this one local cluster; CI shards use independent PostgreSQL services.
No affected migration/fixture file, model or database configuration was changed by
Phase 3. These errors are environmental; no full-suite PASS is claimed and no lock
setting/test gate was weakened. Affected test cases:

- `administration/test_reconciliation.py::test_reconcile_derives_service_claims_from_gbp_snapshot`
- `administration/test_effective_facts.py::test_effective_facts_winner_within_scope_by_authority_and_revision`
- `business_identity/test_service.py::test_resolves_organization_with_profile_and_active_industry`
- `authentication/test_api.py::test_bootstrap_lifecycle_and_authenticated_principal_contract`

Tests not run: existing web browser scenarios (occupied port), live Supabase/Render/
Vercel/OAuth/provider acceptance, real review publication/read-back, actual AI-provider
staging acceptance, production canary, deployed security and staging capacity. These
are not inferred from synthetic results. CI must confirm in its clean environment.

## Live staging and consolidated owner checklist

Every live-only item is `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`.
No live provider read/write, external provisioning, deployment, production SQL,
client asset change, canary or capacity test occurred.

- Confirm inherited Phase 0.5 costs/access, independent Supabase Auth/Postgres,
  backup/restore/telemetry, four Render services and protected Vercel console project.
- Supply independent server-only secrets, exact console/API/Auth origins and hosts,
  DNS/TLS/preview protection and Supabase redirects; retain configured backend console
  OAuth return origin and validate its deployed behavior.
- Run canonical synthetic seed/operator membership/entitlement/location setup and
  independent Google OAuth authorization/refresh. Confirm exact GBP mappings/scopes.
  Retain staging Google write denial; do not copy production tokens.
- Capture deployed Reviews desktop/mobile inventory, stale/partial/reconnect/errors,
  empty/no-evidence versus true zero, scoped draft/AI/new revision, AAL2 approval,
  audit and cross-tenant/cache/CSRF journeys. Verify actual AI provider behavior.
- Real response publication/read-back requires **separate explicit write authorization**
  and a permitted environment. Capture exact revision, policy, workflow/job/audit,
  provider moderation/read-back and ambiguous-write recovery evidence. Synthetic
  dispatch is not permission for a real write.
- Complete inherited Phase 1/2 deployed auth/security, independent Google read smoke,
  dedicated GitHub governed staging publication and measured capacity acceptance;
  publish the immutable baseline tag. Production canary remains a separate later task.

## Unsupported capabilities and scope boundaries

Review-request campaigns, request templates, sends/delivery, campaign performance and
campaign automation have no canonical persisted source and remain unavailable.
Provider-wide review totals/coverage, review velocity/trend and response-rate/time
metrics are unavailable; displayed aggregates describe all persisted reviews only.
Approval-free local client/industry overrides, response rejection/deletion/editing in
place, manual response retry and fabricated review improvement opportunities remain
unavailable. Imported replies are observations, not new locally authorized actions.
Missing author/rating/text/import evidence stays missing, not invented or zero.

Website & Content, Leads, Automations, Reports, Portfolio, Administration and Phase 4
were not migrated. Adjacent generic policy evolution, provider-wide metrics and
manual recovery APIs are recorded here, not implemented as parallel systems.

## Ledger and readiness

Decision log appends D45–D49. Release ledger appends only Command Center Phase 3,
`IMPLEMENTED_NOT_ACCEPTED` for live rollout, linking this artifact and its owner
checklist. No prior acceptance status is rewritten.

`READY FOR PHASE 4 WITH LIVE STAGING ACCEPTANCE PENDING`, subject to review/merge and CI confirmation in a clean environment. Local full-suite acceptance remains limited by the four unrelated PostgreSQL setup errors and the existing-web browser port. True blockers caused by Phase 3: none remaining. Stop at one Phase 3 PR against
main; do not merge or begin Phase 4.

## Exact files changed

- `apps/api/app/main.py`
- `apps/api/app/products/reviews/service.py`
- `apps/api/app/routes/command_center_reviews.py`
- `apps/console/src/adapters/reviews.ts`
- `apps/console/src/components/reviews/ResponseDetail.astro`
- `apps/console/src/components/reviews/Reviews.astro`
- `apps/console/src/layouts/AppLayout.astro`
- `apps/console/src/lib/review-actions.ts`
- `apps/console/src/pages/clients/[clientSlug]/[...workspace].astro`
- `apps/console/src/server/bff.ts`
- `apps/console/src/server/review-routes.ts`
- `apps/console/tests/browser/phase3.spec.ts`
- `apps/console/tests/browser/upstream.mjs`
- `apps/console/tests/fixtures/phase3.json`
- `apps/console/tests/unit/reviews.test.ts`
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/implementation/command-center/DECISION_LOG.md`
- `docs/implementation/command-center/PHASE_03_ACCEPTANCE.md`
- `packages/contracts/openapi.json`
- `packages/contracts/src/generated/api.ts`
- `tests/python/reviews/test_reviews_api.py`
- `tests/python/reviews/test_reviews_ingestion.py`
