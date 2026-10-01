# LILOs Growth Command Center — Production Integration Master Plan

Status: ACTIVE  
Repository: `LilosG/lilos-platform`

Purpose: govern the production integration of the approved LILOs Command Center frontend into the existing LILOs platform without regression, duplication, architecture drift, or frontend-only workarounds.

This document is durable project authority for this migration. It does not replace repository-wide engineering instructions, security rules, `AGENTS.md`, `CLAUDE.md`, current migrations, tests, or verified production contracts.

If this document conflicts with current code, do not improvise. Inspect current merged `main`, tests, migrations, and runtime contracts; record the discrepancy; then use the safest canonical implementation.

---

## 1. Objective

Integrate the approved Astro Command Center into the production LILOs platform while preserving and improving the backend capabilities already completed in Milestones 1, 1B, and subsequent merged fixes.

The integration must preserve tenant isolation, backend permission authority, durable workflows, audit, idempotency, provider-state semantics, governed publishing, build/deploy/live verification, MFA/auth behavior, and operational recovery paths.

The existing backend is the platform authority.

The new Command Center is the product UX authority.

The old frontend is a forensic source for capabilities, edge cases, permissions, reconnect behavior, and non-regression requirements. Its current UX is not the product template.

---

## 2. Non-negotiable backend authority

FastAPI and existing canonical LILOs services remain authoritative for:

- organizations
- locations
- websites
- memberships
- roles
- permissions
- integrations
- provider mappings
- SEO observations
- opportunities
- recommendations and revisions
- `SiteChangeSet`
- approvals
- content publications
- workflows
- jobs
- schedules
- audit records
- idempotency
- provider writes
- GitHub publishing
- build gates
- post-deploy verification
- automations
- reporting truth

Hermes is a reasoning/drafting layer. Hermes is not the database, permission, workflow, provider-write, or audit authority.

Durable async execution remains in the backend worker/scheduler/workflow system.

---

## 3. Frontend authority

The Command Center owns:

- navigation
- information architecture
- presentation hierarchy
- contextual product views
- evidence presentation
- operator interaction
- accessible interaction
- workflow presentation

The frontend does not own:

- business rules
- authorization rules
- provider reconciliation
- secrets
- idempotency
- durable workflow state
- provider credentials
- backend workflow orchestration

No business rule may be moved into Astro solely to avoid improving a backend contract.

---

## 4. Application topology

Migration is parallel, not in-place.

```text
lilos-platform/
  apps/
    web/        existing frontend
    console/    new Command Center
```

`apps/web` remains operational throughout migration.

`apps/console` is introduced as a separate Astro app in the same monorepo and deployed separately until rollout completes.

Do not delete `apps/web` during integration.

After the new console becomes canonical, keep `apps/web` temporarily as rollback. Remove it only in a separate cleanup PR after sustained production verification.

---

## 5. Approved UI baseline

Approved frontend source:

```text
LilosG/lilos-command-center-astro
```

Before integration:

1. verify current `main`
2. run the complete validation suite
3. record exact commit SHA
4. create a permanent UI baseline tag
5. record the SHA/tag in the Phase 0 contract

Once imported into `apps/console`, active development moves to `lilos-platform`.

The standalone frontend repository becomes a frozen visual/product reference.

Do not redesign during integration unless a verified backend contract, accessibility requirement, or approved product requirement requires it.

---

## 6. Rendering architecture

Use Astro SSR on Vercel.

Server responsibilities:

- authenticated initial data loading
- session validation
- tenant context
- coarse route protection
- token refresh
- FastAPI communication
- secure response headers
- same-origin server endpoints

Browser responsibilities may include:

- dialogs
- filters
- accessible controls
- progressive enhancement
- status refresh/polling
- limited optimistic presentation where safe

No authoritative business logic belongs in browser scripts.

---

## 7. Authentication

Target flow:

```text
Browser
  -> host-only secure session cookie
  -> Astro middleware/server
  -> current Supabase user access token
  -> Authorization: Bearer <token>
  -> FastAPI
```

FastAPI remains the permission and AAL/MFA authority.

MFA is server-enforced and server-mediated while retaining a normal interactive browser experience.

Required auth regression coverage:

- sign in
- sign out
- expired session
- refresh
- concurrent refresh
- AAL2 step-up
- valid TOTP
- invalid TOTP
- abandoned enrollment
- redirect after MFA
- chunked/oversized session cookies

---

## 8. Same-origin BFF boundary

Browser code calls explicit same-origin `apps/console` server endpoints.

The console server forwards authenticated requests to FastAPI.

Do not build a generic authenticated proxy.

Forbidden:

```text
/api/proxy?url=<arbitrary upstream>
```

The BFF must:

- use one configured FastAPI upstream
- allow only approved routes/methods
- attach the Bearer token server-side
- propagate correlation/idempotency headers when applicable
- enforce request-size limits
- enforce timeouts
- strip unsafe hop-by-hop headers
- never accept an arbitrary upstream URL
- never log access/refresh tokens

Business logic remains in FastAPI.

---

## 9. CSRF, caching, and tenant isolation

Cookie-backed mutation endpoints require CSRF protection.

Every unsafe console request must use appropriate:

- secure cookie policy
- SameSite policy
- Origin/expected-host validation
- CSRF token where required by the final auth design

Authenticated tenant pages and BFF responses default to:

```http
Cache-Control: private, no-store
```

Do not prerender authenticated tenant pages.

Add tests proving one tenant can never receive another tenant's rendered or cached data.

---

## 10. Authorization

Console route guards perform coarse access control only.

Examples:

- signed in
- portfolio access
- selected organization
- administrative surface availability

FastAPI remains authoritative for the actual action.

Where useful, backend read models should return explicit capabilities such as:

- `canApprove`
- `canEdit`
- `canReconnect`
- `canPublish`

The frontend renders these capabilities. FastAPI still verifies every mutation.

Do not duplicate the backend permission matrix in Astro.

---

## 11. Routing identity

User-facing URLs may use slugs. Internal identity uses UUIDs.

```text
/clients/coco-maya/
  -> resolve canonical active slug
  -> organization UUID
  -> all downstream requests use UUID
```

Requirements:

- active slugs unique
- normalization defined
- safe slug changes/redirects
- no ongoing business logic keyed by display name
- no API authority based on slug after resolution

Duplicate/dead organizations are data hygiene, not routing architecture.

---

## 12. API contracts and generated transport types

FastAPI OpenAPI is transport-contract authority.

```text
Pydantic/FastAPI
  -> OpenAPI
  -> generated TypeScript transport types
  -> tested adapter layer
  -> product-facing view models
```

Generated transport types are committed.

CI regenerates them and fails when committed output is stale.

Do not spread raw transport types directly through UI code.

Product-facing models may include:

- `OpportunityView`
- `AttentionView`
- `ClientOverviewView`
- `AutomationHealthView`
- `ReportReadinessView`

---

## 13. Compatibility during parallel run

While both `apps/web` and `apps/console` use the production API, normal API evolution is additive.

Safe pattern:

```text
add new contract
-> migrate console
-> preserve apps/web
-> verify both
-> remove obsolete compatibility only after apps/web retirement
```

Security/correctness exceptions may require a compatibility adapter, but unsafe behavior must not be preserved merely for compatibility.

Database changes use:

```text
expand -> migrate -> contract
```

because API, worker, scheduler, and Hermes can run mixed versions during deploys.

---

## 14. Opportunity and Attention product model

Approved Opportunity classifications:

- Issue
- Growth Opportunity
- Optimization
- Data & Tracking

`OpportunityView` is a unified read projection.

Do not create a new universal Opportunity write model solely for the UI.

Underlying sources may include canonical records from SEO, Growth, Content, Reviews, GBP, conversion/tracking, or other domains.

Writes remain domain-specific.

`AttentionView` represents operational items requiring human action, including examples such as:

- authorization expired
- reconnect required
- failed sync
- approval waiting
- build blocked
- workflow failure
- response/action required

Workflow runs, jobs, automation runs, and publications remain first-class backend records.

Automations remains its own product area.

---

## 15. State fidelity

Do not flatten authoritative backend state.

Preserve distinctions such as:

- fresh
- stale
- partial
- unavailable
- disconnected
- reconnect_required
- queued
- running
- waiting
- waiting_approval
- retry_scheduled
- blocked
- failed
- ambiguous
- verified

Missing data is not zero. Unknown is not healthy. Disconnected is not provider outage. Blocked is not failed.

---

## 16. Fixtures

Prototype fixtures never become production data.

Production pages/loaders/adapters may not import fixture modules.

Enforce this with lint/module-boundary rules.

Fixtures remain valid only for:

- isolated component tests
- deterministic browser tests
- non-production provider simulators

If no authoritative production source exists, render an explicit unavailable/empty state.

Never silently fall back to sample data.

---

## 17. Provider adapters

Provider simulation plugs into existing provider interfaces.

No scattered environment checks inside product services.

Use explicit implementations, for example:

```text
SearchConsoleProvider
  - GoogleSearchConsoleAdapter
  - FixtureSearchConsoleAdapter

AnalyticsProvider
  - GoogleAnalyticsAdapter
  - FixtureAnalyticsAdapter

GBPProvider
  - GoogleBusinessProfileAdapter
  - FixtureGBPAdapter
```

Production configuration refuses fixture providers.

Use shared provider contract tests.

CI uses recorded real-provider responses for deterministic parsing/contract tests.

Stable staging also runs scheduled read-only live checks against LILOs-owned Google properties to verify current OAuth scopes, token refresh, and upstream compatibility.

---

## 18. Provider write safety

Writes fail closed.

Staging:

- Google/GBP writes disabled
- GitHub writes permitted only to an explicit dedicated test repository

Use provider-specific capabilities/allowlists if the existing global switch cannot express this safely.

Production writes remain governed by canonical permissions, approval, idempotency, and audit.

---

## 19. Environments

### Local

- local console
- local/test API
- local/test DB
- fixture providers

### PR Preview

- Vercel deployment protection
- staging Supabase only
- staging FastAPI only
- staging data only
- fixture providers
- authenticated via staging Supabase
- host-only cookies
- expected preview-host redirect validation
- zero production credentials

### Stable Staging

Canonical hostname:

```text
console-staging.lilosgrowth.com
```

Contains:

- protected SSR console
- staging Supabase Auth
- staging Supabase Postgres
- staging Render API
- staging worker
- staging scheduler
- staging Hermes
- synthetic organizations
- fixture provider adapters
- dedicated GitHub test repo
- independently authorized read-only live Google access for LILOs-owned properties

Stable staging is the authoritative pre-production acceptance environment.

### Production Canary

Uses the production LILOs Growth organization with a dedicated hard-scoped canary page/target.

Do not use ordinary business pages as disposable test targets.

### Production

Real clients and production providers.

---

## 20. Staging data

Do not copy production client data into staging.

Seed representative synthetic organizations through canonical APIs/services.

Required shapes include:

- hospitality single-location
- home-service/SAB
- multi-location
- healthy integrations
- partial integrations
- expired/reconnect state
- provider rate-limit/failure state
- publishing-enabled test organization

Synthetic providers must support deterministic healthy and failure states.

---

## 21. Production canary

The canary proves the real production governed path.

Exact defect is selected only after verifying:

1. defect is deterministically detected
2. selected source representation is safely editable
3. Issue reaches the normal governed recommendation flow
4. deployed HTML actually expresses the defect
5. production crawler reliably discovers the page
6. reset harness can reproduce the condition safely

Prefer a uniquely addressable Astro/TS field over ambiguous empty JSON values.

The reset harness is test infrastructure, not product behavior.

It must:

- be manually triggered
- target only the LILOs Growth repository
- target only the fixed canary file/path
- use a hard-coded known-bad patch
- accept no arbitrary repo/path input
- require explicit confirmation
- create a PR instead of direct main writes
- use normal CI
- record actor/run/commit
- remain inaccessible from the console

The product path only repairs.

---

## 22. LILOs Growth readiness

Production canary readiness and real-Google smoke readiness are separate.

Phase 0 verifies and documents readiness.

Phase 0.5 performs approved setup.

### Production canary readiness

Verify:

- canonical production organization
- website identity
- crawler discovery
- GitHub App installation
- publishing target
- allowed site-change path/prefix
- canary page map
- governed Issue -> recommendation path
- live verification

### Real Google smoke readiness

Verify separately:

- Search Console connection
- Search Console website mapping
- GA4 connection
- GA4 website mapping
- GBP connection if in scope
- token refresh
- scheduled read-only smoke path

A failure in one provider does not block an unrelated publishing canary unless the actual verified flow consumes that provider.

Staging Google authorization must be independent.

Never copy production refresh tokens into staging.

---

## 23. Observability

Preserve existing correlation support.

Verify continuity through:

```text
browser
-> console
-> FastAPI
-> workflow
-> job/worker
-> Hermes
-> publication
-> GitHub
-> live verification
```

Add causation identifiers where missing.

Never log secrets or auth tokens.

---

## 24. Performance

Use measured budgets, not arbitrary infrastructure plan names.

Measure at minimum:

- authenticated page p95
- API p95
- memory
- CPU
- DB pool utilization
- 5xx rate

Initial SSR page loads should normally require approximately 1-3 backend read calls.

More than 3 requires review/justification or a purpose-built read model.

This is a design threshold, not a rigid rule.

Mutations remain canonical domain actions.

Purpose-built aggregate/read endpoints are allowed where they reduce fan-out or prevent frontend inference.

Infrastructure upgrades occur only when measured capacity requires them.

---

## 25. CI and quality gates

Existing `apps/web` gates remain mandatory until retirement.

`apps/console` must meet or exceed them.

Expected gates:

- format
- lint
- TypeScript
- Astro check
- unit tests
- affected Python tests
- build
- Playwright
- axe accessibility
- OpenAPI drift
- fixture-boundary enforcement
- auth/security tests
- CSRF tests
- cross-tenant/cache isolation tests
- migration checks
- dependency vulnerability checks

API contract changes must validate console compatibility even when console source did not change.

Production console deploys only when affected deploy inputs change.

---

## 26. Phase order

### Phase 0 — Integration Contract

No production feature implementation.

Deliver:

- exact baselines
- backend capability inventory
- old frontend non-regression inventory
- screen/value/action mapping
- canonical read/write contract map
- Opportunity/Attention read-model design
- auth/session design
- BFF design
- CSRF/cache/route-guard design
- OpenAPI generation design
- routing design
- environment mapping
- staging specification
- provider simulator design
- canary design
- LILOs Growth readiness assessment
- compatibility policy
- performance budgets
- rollout/rollback plan
- acceptance matrix
- recurring staging cost estimate
- owner-action dependencies

### Phase 0.5 — Safe Integration Environment

Implement:

- staging Supabase
- staging Render API
- staging worker
- staging scheduler
- staging Hermes
- Vercel console staging project
- authenticated protected previews
- stable staging hostname
- environment isolation
- synthetic seed system
- fixture provider adapters
- recorded-provider tests
- scheduled live read-only Google smoke
- dedicated GitHub test repo
- provider-write isolation
- approved LILOs Growth readiness setup where applicable

### Phase 1 — Foundation + Reference Slice

Implement:

- `apps/console`
- workspace/tooling integration
- Astro SSR
- auth/session
- MFA
- BFF
- CSRF
- cache policy
- route guards
- generated transport contracts
- UI adapters/view models
- tenant/client context
- loading/error/empty states
- OpportunityView
- AttentionView
- canonical Opportunity detail
- evidence
- recommendation
- protected-signal validation presentation
- revise/edit
- approval
- workflow state
- PR/build/deploy state
- live verification

Complete the entire slice in staging.

This becomes the reference pattern.

### Phase 2 — Integrations + Local Search

### Phase 3 — Reviews

### Phase 4 — Website & Content

### Phase 5 — Leads / Conversion Outcomes

### Phase 6 — Automations

### Phase 7 — Reports

### Phase 8 — Client Overview + Portfolio

### Phase 9 — Administration / Settings / Onboarding

Detailed scope for later phases is refreshed from current merged `main` after the preceding phase.

---

## 27. Production rollout

After staging acceptance:

1. production LILOs Growth canary
2. capacity acceptance
3. operator-only rollout
4. internal LILOs users
5. selected client cohort
6. wider client cohort
7. console becomes canonical
8. keep `apps/web` as rollback
9. sustained verification
10. separate cleanup PR removes `apps/web` and obsolete compatibility

Every rollout stage must be reversible.

---

## 28. Prohibited shortcuts

Do not:

- rebuild backend logic in Astro
- introduce duplicate sources of truth
- create a universal Opportunity write table for UI convenience
- use prose matching for backend state
- hide missing data as zero
- flatten typed states
- create blanket approval gates
- bypass tenant isolation
- bypass audit
- bypass idempotency
- expose provider credentials to the browser
- expose production data to staging
- copy production refresh tokens to staging
- build a generic BFF proxy
- allow previews to use production credentials
- directly reset the canary on main
- test mutations against real client assets
- preserve old UX solely because it exists
- import prototype fixtures into production paths
- add one-off frontend workarounds for missing backend contracts
- make undocumented breaking schema/API changes
- remove `apps/web` before rollback is no longer needed
- silently defer required scope
- introduce unapproved side projects
- introduce unnecessary approval checkpoints inside a phase

---

## 29. Execution discipline

Each phase:

1. starts from merged `main`
2. uses one feature branch
3. re-reads this master plan
4. re-reads current code/tests/contracts
5. verifies assumptions against implementation
6. completes one coherent vertical scope
7. runs all relevant gates
8. produces one reviewable PR
9. documents exact changes
10. documents known gaps
11. never claims tests not run
12. does not merge automatically unless explicitly instructed

Do not stop repeatedly for routine choices already governed by this plan.

Stop only for:

- destructive production action
- paid infrastructure approval
- external OAuth/account authorization
- unavailable secrets
- a genuine architecture conflict not covered here

---

## 30. Definition of done

Migration is complete only when:

- every approved Command Center screen uses authoritative production data or an explicit unavailable state
- intended actions reach canonical backend mutations
- permissions remain authoritative
- tenant isolation is proven
- auth/MFA regressions are covered
- Opportunities/Attention are unified read experiences without duplicate write systems
- workflow/automation state remains durable
- provider integrations are represented correctly
- reporting truth is preserved
- governed publishing is verified
- no production fixture dependency remains
- accessibility gates pass
- security gates pass
- performance budgets pass
- production canary passes
- rollout completes successfully
- rollback remains available until stability is established
- `apps/web` is retired only in a separate cleanup step

Correctness, maintainability, and product quality take priority over speed, but do not introduce ceremonial gates, artificial packet splitting, or unnecessary rework.
