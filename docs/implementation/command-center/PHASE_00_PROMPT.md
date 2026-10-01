# Phase 0 — Command Center Integration Contract

## Role

You are executing Phase 0 of the LILOs Growth Command Center production integration.

Repository: `LilosG/lilos-platform`

Start from current merged `main`.

Before any work:

1. Read root `AGENTS.md` and `CLAUDE.md` where present.
2. Read `docs/implementation/command-center/MASTER_PLAN.md` in full.
3. Inspect current merged code, migrations, tests, and configuration.
4. Inspect the approved Command Center source in `LilosG/lilos-command-center-astro`.
5. Do not rely on stale chat context or old branch assumptions.

## Objective

Produce an implementation-grade integration contract for the new Command Center.

This phase is discovery, verification, architecture mapping, and acceptance planning.

It is not product implementation.

Do not:

- create `apps/console`
- wire production screens
- change production workflow behavior
- mutate production data
- provision paid infrastructure
- connect accounts
- redesign the approved frontend
- begin Phase 0.5

## Required outputs

Create:

```text
docs/implementation/command-center/PHASE_00_INTEGRATION_CONTRACT.md
docs/implementation/command-center/ACCEPTANCE_MATRIX.md
docs/implementation/command-center/DECISION_LOG.md
```

## A. Baselines

Record:

- exact `lilos-platform` main SHA
- exact `lilos-command-center-astro` main SHA
- current frontend validation status
- recommended permanent UI baseline tag
- relevant framework/runtime/tooling versions
- current deployment topology
- current auth model
- current worker/scheduler/Hermes topology

## B. Old frontend non-regression inventory

Inspect `apps/web` enough to identify every meaningful capability that could disappear during migration.

At minimum inspect:

- sign in/out
- Supabase session behavior
- token refresh
- MFA/AAL2
- org/client selection
- admin-only routes
- onboarding
- integration reconnect
- provider mapping
- async workflow status
- polling
- retries/recovery
- approval behavior
- integration diagnostics
- permission/capability handling
- typed failure states
- reporting
- automations
- reviews
- leads
- content
- SEO
- GBP
- GSC
- GA4

For each capability classify:

```text
KEEP
REPLACE UX
MOVE
RETIRE WITH REASON
```

Do not preserve old UX simply because it exists.

## C. New console screen contract

For every approved Command Center screen and every meaningful value/action, map:

- UI capability
- authoritative backend model
- read endpoint/read model
- mutation endpoint
- org/location scope
- required permission/capability
- freshness semantics
- async workflow behavior
- typed blocker/error states
- audit behavior
- idempotency behavior
- UI representation
- current fixture being replaced
- acceptance journey

If no authoritative source exists, record:

```text
NO SOURCE — EXPLICIT EMPTY STATE
```

Do not invent data.

## D. Opportunity and Attention contract

Define a unified `OpportunityView` read projection with approved classifications:

- Issue
- Growth Opportunity
- Optimization
- Data & Tracking

Define a separate `AttentionView` for operational attention.

Do not create a new universal write model.

Identify:

- every canonical backend source feeding each projection
- stable source identifiers
- durable IDs
- product area
- classification mapping
- allowed actions
- evidence mapping
- status mapping
- domain mutation route for each action
- workflow/publication references

Workflow runs, jobs, automation runs, and publications remain first-class records.

## E. Auth and security design

Document exact design for:

- Astro SSR session
- Supabase SSR
- token refresh
- MFA/AAL2
- host-only cookies
- secure cookie flags
- Preview auth
- stable staging auth
- same-origin BFF
- explicit BFF routes
- upstream allowlisting
- request size/timeouts
- CSRF
- route guards
- cache-control
- cross-tenant isolation
- redirect-host validation
- token/logging rules

Do not design a generic proxy.

## F. OpenAPI and type generation

Define:

```text
FastAPI/Pydantic
-> OpenAPI
-> generated TS transport types
-> tested adapter layer
-> UI view models
```

Specify:

- generator
- output path
- generation command
- committed generated files
- CI stale-contract check
- adapter test strategy

## G. API and DB compatibility

Document the compatibility window while both `apps/web` and `apps/console` run.

Default API rule: additive first.

Document the exception process for security/correctness fixes.

Document DB:

```text
expand -> migrate -> contract
```

Identify current contracts likely to need adapters.

## H. Slug/UUID routing

Define:

```text
slug -> canonical active org UUID -> UUID-based downstream calls
```

Verify active-slug uniqueness behavior.

Separate duplicate/dead organization hygiene from routing architecture.

## I. Environment matrix

Define exact Local / Preview / Staging / Production Canary / Production topology.

Preview must use only staging:

- Supabase
- API
- data
- providers
- credentials

Stable staging must use:

- separate Supabase Auth
- separate Supabase Postgres
- staging Render API
- staging worker
- staging scheduler
- staging Hermes
- protected Vercel console
- stable `console-staging.lilosgrowth.com`
- synthetic organizations
- fixture adapters
- GitHub test repo

Verify appropriate Vercel runtime/region from actual topology.

## J. Provider test architecture

Inspect existing provider interfaces/adapters.

Design fixture adapters through the canonical seams.

No environment checks inside product services.

Define:

- synthetic healthy responses
- expired auth
- rate limit
- partial response
- unavailable provider
- missing mapping
- recorded-response CI
- shared adapter contract tests
- scheduled live read-only smoke
- production ban on fixture adapters
- provider-specific write safety
- GitHub staging allowlist

## K. LILOs Growth readiness

Assess separately:

### Production canary readiness

Verify current state for:

- production organization
- website
- crawler discovery
- GitHub App
- publishing target
- allowed path/prefix
- page map
- governed Issue -> recommendation -> change flow
- live verification

### Real Google smoke readiness

Verify current state for:

- GSC connection
- GSC website mapping
- GA4 connection
- GA4 website mapping
- GBP if in scope
- token refresh
- scheduled read-only smoke

Do not perform setup in Phase 0.

## L. Production canary qualification

Verify an actual deterministic canary candidate.

Required checks:

1. detector exists
2. selected source type can be edited safely
3. Issue reaches normal governed recommendation flow
4. deployed HTML expresses the defect
5. production crawler discovers the page
6. reset harness can recreate the condition safely

Empty `current_value` is supported at the SiteChangeItem model layer; verify source-specific resolver/edit safety.

Prefer uniquely addressable Astro/TS state over ambiguous empty JSON values.

Design the reset harness:

- manual trigger
- fixed LILOs Growth repo
- fixed file/path
- fixed known-bad patch
- confirmation input only
- PR-based
- audited
- never exposed in console

## M. Performance budget

Define measurable initial budgets for:

- SSR page p95
- API p95
- memory
- CPU
- DB pool
- 5xx

Identify screens with likely excessive read fan-out.

1-3 initial backend reads is the normal target, not a rigid limit.

Identify where aggregate read models are justified.

Do not prescribe a paid plan without measurements.

## N. CI contract

Define required gates for `apps/console`.

At minimum:

- format
- lint
- TS
- Astro check
- unit
- build
- Playwright
- axe
- OpenAPI drift
- fixture-boundary enforcement
- auth tests
- CSRF tests
- tenant/cache isolation
- affected backend tests
- migration checks
- vulnerability audits

`apps/web` gates remain mandatory until retirement.

## O. Cost and owner-action requirements

Identify:

- new recurring staging cost
- paid choices
- Supabase project requirement
- Render resources
- Vercel requirements
- OAuth actions
- DNS actions
- GitHub App actions
- secrets unavailable to the coding agent

Do not provision them.

## P. Final implementation phase contract

From verified current `main`, refine scopes for:

- Phase 0.5
- Phase 1
- Phase 2
- Phase 3
- Phase 4
- Phase 5
- Phase 6
- Phase 7
- Phase 8
- Phase 9
- staging acceptance
- canary
- gradual rollout
- rollback
- cleanup

Do not create unnecessary extra phases.

## Evidence standard

Every conclusion must be labeled as one of:

```text
VERIFIED CURRENT FACT
PROPOSED DESIGN
BLOCKER
OWNER ACTION REQUIRED
```

Tie verified facts to actual code/tests/config.

Do not claim behavior you did not verify.

## Completion report

At the end report:

1. exact files created/changed
2. exact baseline SHAs
3. verified architecture
4. blockers
5. owner actions
6. estimated recurring staging costs
7. whether Phase 0.5 is `READY` or `BLOCKED`
8. exact reason for any blocked item

Do not begin Phase 0.5.
Do not merge automatically.
