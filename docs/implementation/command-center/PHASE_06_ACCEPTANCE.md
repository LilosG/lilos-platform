# Phase 6 — Automations acceptance

State: `IMPLEMENTED_NOT_ACCEPTED` for live rollout.
Live staging: `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`.
Full-repository acceptance gate: **GitHub CI, pending the Phase 6 PR**.

## Repository state and canonical reuse

Started on clean `command-center/phase-6` at the supplied stable Phase 5 head
`52a6def1ebe63041190db5f68b65d097b36c1725`. Initial verification was limited to
branch, status and five-commit log. Required repository instructions and Command
Center plans/contracts/Phase 0–5 acceptance/decision/follow-on documents were read.
Governing documents are present. All work is confined to `lilos-platform-phase6`;
other worktrees were not modified or switched.

Reused ExecutionService and the fixed WORKFLOW_TYPES registry, WorkflowDefinition,
WorkflowVersion, WorkflowRun, Schedule, Job, JobAttempt, AgentRun, canonical agent
eligibility/controls, ContentPublication read-back, AuthorizationService and audit
records. Existing Astro SSR/session/MFA/context, closed same-origin BFF, generated
OpenAPI, adapters and approved shell/panels/tables/dialogs remain authoritative.
No model, migration, dependency, worker, scheduler, provider configuration or hosting
architecture was changed. Hermes remains reasoning rather than database/workflow authority.

Evidence-backed gaps: the console Automation placeholder; fragmented untyped
operational reads; no scoped heartbeat source; no generic safe manual retry contract;
no rank-scan/monthly-report workflow source or client definition-activation mutation.

## Implementation

Two additive typed read endpoints under
`/api/v1/organizations/{organization_id}/command-center/automations`:

- Workspace: registered definition/version state, optional UUID location scope,
  canonical agent eligibility for that location, independently authorized schedules,
  persisted next/last dispatch/timezone, 50 paginated recent runs, an independent
  bounded attention query and ten recent completed execution candidates. Attention
  is independent of history pagination. All reads use persisted records without
  provider I/O. Source quality remains partial and worker/scheduler health unavailable.
- `/runs/{run_id}`: exact scoped run, job states, retry availability, failure/blocker
  codes/categories, correlation/idempotency, up to 50 jobs/100 attempts and 50
  permission-gated audit events. Agent controls reflect actual persisted status,
  native run identity, capability snapshot and backend workflows.manage permission.
  Current approval evidence is supplied only to an authorized controller.

Production workspace presents Requires Attention, Upcoming Important Runs, Recent
Meaningful Outcomes, Operational Health and All Automations, plus the run dialog.
The portfolio Automations route selects an authorized client; it creates no portfolio
aggregate. Schedule state is separate from shared definition activation. Unscheduled
workflows have no fabricated next-run time. Paused/cancelled stored next times are
explicitly inactive; last dispatch is not presented as last successful completion.

Closed BFF actions reuse canonical standalone GBP sync/Reviews ingestion, explicit
schedule creation/status/configuration updates, scoped eligible agent start and native
stop/steer/one-time approval/denial. Schedule creation requires an operator-supplied
first-dispatch timestamp; subsequent dispatch is solely the backend scheduler's job.
The screen exposes pause/resume and creation for the two standalone scheduled workflows.
Product publication/recovery remains in its owning product via links to the already
integrated canonical controls. No arbitrary workflow/payload replay or manual retry
endpoint was introduced. Definition activation remains read-only.

PATCH uses the same strict body, UUID/query, bounded-input, current server Bearer,
correlation, CSRF/session binding, exact Origin/host, no redirect/unsafe header,
timeout/no automatic replay and private/no-store protections as existing mutations.
Backend permission and tenancy checks remain authoritative. Production imports no
reference/test fixtures. Browser simulation exists only under tests.

## State and outcome fidelity

- Queued/running/waiting/approval/retry/partial/cancelled/expired/failed/escalated and
  completed execution states are preserved independently from job/agent/publication state.
- Recorded output from a completed non-publication execution is an execution result,
  explicitly **not** verified provider or business success. No output means execution
  state only. Provider-writing workflows without canonical read-back stay unconfirmed.
- Content/site-change publication success requires completed workflow, canonical
  publication `verified` and persisted `verified_at`; checks/merge/deploy alone never
  establish success. Failed/checks-failed/reconciliation-required stay attention.
- Retry time comes only from a retry_scheduled Job.available_at; attempt budgets and
  histories are durable worker evidence. No browser retry policy exists.
- A created/queued/running workflow unchanged for 24 hours is labeled stale observation,
  not inferred worker death. An active next dispatch over five minutes overdue is
  schedule attention, not proof of provider failure. Both thresholds are backend-only
  read classification and never change durable state or calculate dispatch time.
- Attention/history/outcome bounds are disclosed. No exceptions in returned records
  does not claim healthy runtime or complete provider coverage. Missing schedules
  permission is unavailable, rather than a claim of zero schedules.

## Repository/synthetic acceptance

| Scenario                                                    | Result / evidence                                                                                                                                          |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Definition activation and active/paused schedules           | PASS — persisted API projection, adapter and desktop/mobile inventory                                                                                      |
| Scheduled versus unscheduled, next/last dispatch            | PASS — canonical schedule API, adapter and browser; no computed next dispatch                                                                              |
| Queued/running/completed/failed and partial/waiting/stale   | PASS — canonical API state matrix, adapters and browser                                                                                                    |
| Reconciliation before success                               | PASS — actual projection tested against reserved/checks/deploy/reconciliation/failed/verified domain records; missing verified timestamp fails unconfirmed |
| Attention classification and durable retries                | PASS — API failure/retry/stale, typed adapter and browser; initial canonical recovery regressions passed                                                   |
| Operational health                                          | PASS — explicit unavailable scoped heartbeat and partial coverage; no inferred Healthy                                                                     |
| Run/job/attempt/audit history and correlation/idempotency   | PASS — canonical API duplicate enqueue retains one job/run, detail tests and browser evidence                                                              |
| Supported schedule creation/pause/resume and agent steering | PASS — exact-body desktop/mobile BFF journeys; canonical services remain the action authority                                                              |
| Retry/recovery boundary                                     | PASS — unsupported generic retry/unknown workflow routes rejected; owning-product recovery links retained                                                  |
| Partial/unavailable/error states                            | PASS — API/adapter null/state fidelity and desktop/mobile unavailable/error journeys                                                                       |
| Wrong tenant/location/run and anonymous access              | PASS — canonical API, adapter scope negatives and closed BFF/browser/cache checks                                                                          |
| CSRF/Origin/host/cache and closed BFF                       | PASS — focused security units, strict PATCH/body/query checks and browser forgery denial                                                                   |
| No production fixture authority                             | PASS — production import-boundary script and negative boundary tests                                                                                       |
| Desktop/mobile and accessibility                            | PASS — eight distinct Phase 6 scenarios with axe; screenshots inspected                                                                                    |

API tests use a dedicated disposable PostgreSQL 17 cluster on
`127.0.0.1:55526/lilos_phase6_test`; no Supabase/production database was used.
Browser tests use real console SSR/auth/BFF/UI with isolated synthetic upstream HTTP.
These are repository proofs, not live staging/provider acceptance.

## Focused validation actually run

- Phase 6 Python file: **3 PASS**. Before the acceleration directive, focused
  Automation/scheduling/recovery regressions plus the original two Phase 6 cases:
  **35 PASS**, one inherited Starlette deprecation warning. No complete Python suite.
- Phase 6 console unit file: **5 PASS**. Focused foundation security/boundary plus
  Phase 6 units: **31 PASS** after correcting new test CSRF argument order.
- Phase 6 browser/axe: **eight distinct desktop/mobile cases PASS** after correcting
  Astro formatter omissions (heading slots/job evidence) and a queued-cell locator.
  The dedicated focused runner uses ports 4347/4456, leaves prior listeners alone and
  keeps the same scenarios compatible with default CI ports 4346/4455.
- Console Astro/TypeScript: PASS, no errors/warnings; four inherited deprecated
  navigation hints. Console SSR build: PASS. Local Node 22.17.1 dependency install
  retains the inherited undici newer-patch warning; deployment/CI pins unchanged.
- OpenAPI drift: PASS. Structural comparison: exactly **two added paths/nine added
  schemas**, zero modified/removed existing contracts.
- Changed-file Ruff/format/mypy/ESLint, production fixture boundary and
  `git diff --check`: PASS.

The owner's acceleration directive makes GitHub CI the final full-repository gate.
Complete local Python/inherited browser/full-release suites were intentionally not
run. No CI result for Phase 6 is claimed before it exists. Existing CI remains intact.

## Sequencing

Phase 5 merged at `614b8188e6285eedeffbe85fe574d5e6272085d2`; owner reported
main CI #764 green. Fetch verified origin/main at that exact merge SHA. The Phase 6
checkpoint was rebased with `git rebase --onto origin/main 52a6def1ebe63041190db5f68b65d097b36c1725 command-center/phase-6`, replaying only this phase's commit and preserving the already-squashed Phase 5 work.
Rebased implementation checkpoint: `07e222b`. No conflicts; the complete tracked
implementation tree is identical before/after rebase. The diff against actual
origin/main contains exactly the 22 Phase 6 files below; `git diff --check` passes.
No affected-code revalidation was needed after this unchanged rebase. Final docs
record the evidence before branch push/PR creation. Phase 6 GitHub CI remains the
pending full-repository gate. Phase 7 has not begun.

## Unsupported capabilities, adjacent work and live staging

No-source runtime heartbeat/provider-wide health/SLA/complete coverage, rank scans,
monthly report automations, generic manual retry, blind provider-write replay,
client-level definition activation and fabricated next-run predictions remain
unavailable. Missing domain publication read-back never becomes success. Definition
activation is shared registry state, with no invented client toggle. Existing product
reconciliation/recovery is reused rather than duplicated in Automation.

All live-only items remain `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`:
independent Supabase Auth/Postgres and secrets, protected console and four Render
services, exact hosts/origins/DNS/TLS, seed/membership/entitlement/mapping setup,
independent provider authorization/read smoke, deployed worker/scheduler dispatch,
actual agent/runtime capability acceptance, deployed schedule/failure/recovery/tenancy/
CSRF/cache/accessibility journeys, audit/correlation and measured capacity evidence.
Inherited dedicated GitHub read-back/baseline-tag/canary owner steps remain separate.
No staging provisioning or real provider/client mutation was performed or authorized.

Decision log appends D59–D62. Release ledger appends only Phase 6,
`IMPLEMENTED_NOT_ACCEPTED`, linking this artifact and pending live checklist; prior
statuses are unchanged. Missing heartbeat/definition controls and unsourced workflow
families are recorded adjacent gaps, not additional implementation packets. Leads,
Website & Content, Reviews, Local Search, Reports, Portfolio aggregates,
Administration/Settings/Onboarding and Phase 7 were not expanded.

True repository implementation blockers: none after focused checks. Full Phase 6
acceptance awaits GitHub CI/review; live staging awaits owner resources/evidence.
Phase 7 remains deferred until Phase 6 review/CI/merge and is not started here.

## Exact files changed

- `apps/api/app/main.py`
- `apps/api/app/routes/command_center_automations.py`
- `apps/console/playwright.phase6.config.ts`
- `apps/console/src/adapters/automations.ts`
- `apps/console/src/components/automations/Automations.astro`
- `apps/console/src/components/automations/RunDetail.astro`
- `apps/console/src/layouts/AppLayout.astro`
- `apps/console/src/lib/automation-actions.ts`
- `apps/console/src/pages/[...page].astro`
- `apps/console/src/pages/clients/[clientSlug]/[...workspace].astro`
- `apps/console/src/server/automation-routes.ts`
- `apps/console/src/server/bff.ts`
- `apps/console/tests/browser/phase6.spec.ts`
- `apps/console/tests/browser/upstream.mjs`
- `apps/console/tests/fixtures/phase6.json`
- `apps/console/tests/unit/automations.test.ts`
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/implementation/command-center/DECISION_LOG.md`
- `docs/implementation/command-center/PHASE_06_ACCEPTANCE.md`
- `packages/contracts/openapi.json`
- `packages/contracts/src/generated/api.ts`
- `tests/python/workflows/test_command_center_automations.py`
