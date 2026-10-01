# Phase 5 — Leads / Conversion Outcomes acceptance

State: `IMPLEMENTED_NOT_ACCEPTED` for live rollout.
Live staging: `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`.

## Repository state and canonical reuse

Started on clean `command-center/phase-5` at the supplied stable Phase 4 head
`2d88927b4ad43778d428720d345aa547bd0cb277`. The only initial verification was
branch, status and five-commit log. Required repository instructions and Phase 0–4
integration/acceptance/decision/follow-on documents were read. Governing documents
are present. All work is confined to `lilos-platform-phase5`; other worktrees were
not modified or switched. This parallel Phase 5 implementation follows the user's
explicit sequencing exception; PR creation and broad final gates require actual
Phase 4 merge and rebase first.

Reused LeadService and canonical Lead, LeadSource, LeadSubmission, consent,
suppression, assignment, status history, conversion/loss, notes/tasks, communication,
CRM mapping and audit records. Existing AccessControlService supplies assignable
members. Backend authorization/AAL, canonical durable workflows/worker dispatch,
provider delivery reconciliation and idempotency remain authoritative. Existing
console SSR/session/MFA/context/BFF/security and approved panels/tables/dialog shell
are reused. No second CRM/store, model, migration, provider adapter, attribution
engine, deployment change or provider configuration was introduced.

Evidence-backed gaps: console Leads placeholder; untyped, fragmented operational
reads; list/detail lacking source/submission identity; no measured downstream booking,
sales/jobs/revenue or campaign/page attribution source. The latter remain unavailable.

## Contracts and implemented journeys

Two additive typed reads under
`/api/v1/organizations/{organization_id}/command-center/leads`:

- Workspace: optional canonical organization-owned UUID location, 50 PII-free lead
  inventory records with deterministic pagination, all persisted scope counts,
  recorded conversions, location choices and up to 100 source evidence rows. Batched
  source aggregates read canonical submissions/connections/provider identity. Source
  rows are partial; no claim of complete provider coverage or unique customer counts.
- `/{lead_id}`: optional location must match the canonical lead. Contact/message,
  source/provider identity, receipt/contact/delivery/conversion timestamps, recorded
  value/loss, duplicates, submissions/external IDs, CRM mapping state, bounded histories,
  consents, communications and canonical workflow state are returned. Each history
  section is limited to 50 records, newest first, and explicitly partial. Audit history
  requires canonical `audit.read`; action capabilities are evaluated by the backend.

`LeadsWorkspace` and `LeadWorkspaceDetail` use typed nested DTOs, committed generated
OpenAPI/TypeScript transport and tested UI adapters. Existing paths/schemas are
unchanged: two added paths and 14 added schemas. No old-web contract changed.

Production `/clients/{slug}/leads/`, `/leads/outcomes/` and `/leads/{UUID}/` render
canonical inventory, source evidence, metrics and detail in the approved shell.
Location selection/pagination preserve UUID scope. Bulk list contact PII remains
in detail. Known lead conversions/losses use actual persisted evidence; unfinished
leads explicitly show unknown outcome. Archived conversions retain their recorded
conversion timestamp and count rather than losing historical evidence.

Closed BFF allows these reads and only existing canonical assignment/status,
conversion/loss, notes, tasks/completion, consent and communication actions. Strict
bodies, bounded inputs, UUID scope, server Bearer/correlation, CSRF/session binding,
Origin/host protection, timeout/no automatic replay and private/no-store responses
remain intact. Source provisioning/secrets/rotation and machine intake are not exposed
through console Leads; external system configuration remains in Integrations.

The UI uses existing canonical services for every action. Conversion is explicitly
an operator-recorded lead assertion, not independently verified revenue or a booking.
Consent evidence requires actual source/disclosure/reference/time and backend AAL2;
communication eligibility/suppression remain backend decisions. Planned/queued/sent
work never becomes delivered in Astro. No provider/client mutation was performed.

## Truthful source and outcome semantics

- Counts describe **all persisted lead records in the selected scope**, including
  duplicate records. No period multiplier, pagination-derived total, GA4 event total,
  channel overlap aggregation, provider-wide total or attribution heuristic is used.
- No source/intake evidence yields null/unavailable counts. A configured source with
  an empty canonical store supports true zero **recorded** leads/conversions; this is
  never described as proof of zero events at an external provider.
- `last_intake_at` is canonical submission receipt time, distinct from upstream lead
  received time. Intake older than 24 hours is labeled stale recency, explicitly not
  sync health or tracking failure. Last sync remains unavailable: no canonical lead
  sync record exists. Persisted degraded/reconnect/error connection state is retained.
- Intake source identity and linked provider/connection are evidence. Missing provider
  is unknown; campaign, landing-page and channel attribution remain unavailable.
  CRM external mapping/sync state is displayed without inferring downstream results.
- Conversion timestamps, loss evidence, human contact and delivery timestamps remain
  independent. Nullable recorded value stays unavailable and does not establish
  measured revenue. No currency/revenue aggregate is invented.
- Website & Content / Conversions continues to own site journey/friction/CTA/path
  behavior. Leads does not consume or sum GA4 events, GBP interactions or click intent
  as measured business outcomes. The conversion-path link preserves this boundary.

## Repository / synthetic acceptance

| Scenario                                        | Result / evidence                                                                                   |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Lead inventory and detail                       | PASS — canonical API, generated transport, typed adapters, desktop/mobile SSR/dialog                |
| True zero versus unavailable                    | PASS — empty canonical source/store vs no source; adapter and browser scenarios                     |
| Missing attribution/provider                    | PASS — explicit unknown/null provider and unavailable campaign/page evidence                        |
| Stale/partial/degraded/reconnect/error          | PASS — persisted API source evidence, adapter and synthetic browser source/error states             |
| Known versus unknown outcome                    | PASS — canonical conversion/archive timestamps and unknown unfinished lead                          |
| No fabricated downstream outcome                | PASS — typed unavailable downstream contract; unknown bookings/sales/jobs/revenue retained          |
| Source/provider/submission identity             | PASS — real persisted provider/connection projection and external submission IDs                    |
| Duplicate/idempotent intake                     | PASS — repeated source/submission reuses one canonical lead/submission; original services unchanged |
| Wrong tenant/location and unauthenticated       | PASS — backend, adapters, closed BFF and warmed browser scope/cache negatives                       |
| Consent, suppression and communication delivery | PASS — canonical API/dispatch regressions; planned/queued not delivered in UI                       |
| Assignment/status/notes/tasks/conversion        | PASS — canonical API/assignee regressions and browser exact-body operational journeys               |
| Closed BFF/CSRF/origin/host/private cache       | PASS — focused unit/security suite and browser forgery/query/cache negatives                        |
| No fixture authority                            | PASS — production boundary script and negative boundary tests; fixtures confined to tests           |
| Desktop/mobile and accessibility                | PASS — real console SSR/auth/BFF with isolated HTTP upstream; axe and inspected screenshots         |

Synthetic browser HTTP responses and disposable PostgreSQL tests provide different
repository proofs. Neither establishes live provider or deployed staging acceptance.

## Validation actually run

- Canonical targeted command: `tests/python/leads/test_command_center_leads.py`,
  `test_leads_api.py`, `test_lead_communication_dispatch.py`,
  `test_leads_assignees_api.py`: **23 PASS**, one inherited Starlette warning.
  Final provider/stale/history batching amendments additionally pass the two
  projection cases. Tests use only dedicated local PostgreSQL 17 at
  `127.0.0.1:55525/lilos_phase5_test`.
- Focused console Leads/security/boundary tests: **31 PASS** across three files.
- Phase 5 desktop/mobile browser scenarios with axe: **10 distinct scenarios PASS**: eight initial inventory/detail/outcome/security
  cases and two additional assignment/task/AAL2-consent/communication journeys.
- Changed-file Ruff/format/mypy/ESLint/Prettier, production import-boundary script,
  console Astro/TypeScript and console SSR build: PASS. Four inherited Phase 2
  deprecated-navigation hints remain; no new errors/warnings.
- `npm run contracts:check`: PASS; structural comparison proves only the two new
  Leads paths/14 new DTOs. No model/migration/dependency/hosting change.

Initial new import/membership/mock typing and browser contrast/scenario setup issues
were corrected with focused checks. Two early DB commands accidentally shared one
migration fixture database; catalog/missing-table collisions were a harness error.
Sequential targeted rerun passed; no product repair or test weakening was required.
`agent-browser` is unavailable; repository Playwright/axe supplies browser verification.
No broad repository suite has run before the Phase 4 merge prerequisite.

## Final sequencing

Phase 4 merge/rebase and broad final gates are pending verification at commit time.
Do not claim final acceptance or open a Phase 5 PR until Phase 4 PR #146 is confirmed
merged, the branch is rebased onto actual `origin/main`, and the Phase 5-only diff is
reviewed. If Phase 4 is unmerged, push the committed branch and stop with
`WAITING FOR PHASE 4 MERGE`. Never merge or begin Phase 6.

## Unsupported capabilities and live staging

Retained explicit unavailable/unknown: completed reservations/bookings, sales,
booked/completed jobs, measured revenue, call-tracking outcomes, external CRM outcome
sync, fake campaign/channel/page attribution, provider-wide totals/comparison trends,
unique customer counts and source last-sync/complete coverage. Contact/communication
and form-intake evidence is shown only where persisted. No new integrations invented.

All live-only items remain `PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`:

- Inherited Phase 0.5–4 independent Supabase Auth/Postgres, protected console/Vercel,
  four Render services, independent server-only secrets, exact hosts/origins,
  DNS/TLS/redirects, backup/restore/telemetry and measured capacity evidence.
- Canonical synthetic seed/operator membership/entitlement/location setup and
  independently authorized provider read access. No production data/token copy.
- Deployed Leads desktop/mobile inventory/detail/outcomes, actual sourced intake,
  missing/zero/stale/partial/error, tenant/location/cache/CSRF/AAL2 and accessibility
  journeys. Capture actual persisted source/submission/audit/workflow evidence.
- Real communication delivery/provider/client writes require separate explicit
  authorization and a permitted environment. This packet authorizes none of them.
  Retain inherited staging Google write denial and exact GitHub test-only scope.
- Inherited independently authorized Google read smoke, dedicated governed GitHub
  publication/read-back, immutable UI baseline tag and later qualified canary steps.

True repository implementation blockers: none remaining. Phase 6 requires Phase 5
review, clean CI/final gate confirmation and merge; live staging remains pending.
No Phase 6 implementation was started.

## Ledger and adjacent work

Decision log appends D55–D58. Release ledger appends only Command Center Phase 5,
`IMPLEMENTED_NOT_ACCEPTED`, linking this evidence and pending owner checklist.
Prior statuses are not rewritten. Unsupported downstream measurement/attribution and
lead-source sync observability are adjacent recorded gaps, not new provider work.
Website & Content, Reviews, Local Search, Automations, Reports, Portfolio aggregates,
Administration/Settings/Onboarding and Phase 6 are not expanded by this packet.

## Exact files changed

- `apps/api/app/main.py`
- `apps/api/app/routes/command_center_leads.py`
- `apps/console/src/adapters/leads.ts`
- `apps/console/src/components/leads/LeadDetail.astro`
- `apps/console/src/components/leads/Leads.astro`
- `apps/console/src/layouts/AppLayout.astro`
- `apps/console/src/lib/lead-actions.ts`
- `apps/console/src/pages/clients/[clientSlug]/[...workspace].astro`
- `apps/console/src/server/bff.ts`
- `apps/console/src/server/lead-routes.ts`
- `apps/console/src/styles/app.css`
- `apps/console/tests/browser/phase5.spec.ts`
- `apps/console/tests/browser/upstream.mjs`
- `apps/console/tests/fixtures/phase5.json`
- `apps/console/tests/unit/leads.test.ts`
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/implementation/command-center/DECISION_LOG.md`
- `docs/implementation/command-center/PHASE_05_ACCEPTANCE.md`
- `packages/contracts/openapi.json`
- `packages/contracts/src/generated/api.ts`
- `tests/python/leads/test_command_center_leads.py`
