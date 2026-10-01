# Phase 1 — Console Foundation + Opportunities/Attention Reference Slice

## Preconditions

Start only after Phase 0 and Phase 0.5 are merged and accepted.

Read:

- `MASTER_PLAN.md`
- completed Phase 0 integration contract
- acceptance matrix
- decision log
- Phase 0.5 acceptance
- current merged `main`
- current approved UI baseline

## Objective

Create `apps/console` and complete one production-grade reference vertical slice:

```text
authenticated user
-> organization/client context
-> Opportunity/Attention
-> evidence
-> recommendation
-> deterministic quality state
-> revise/edit
-> approve
-> workflow
-> PR
-> build gate
-> merge/deploy
-> live verification
```

This phase establishes the architecture pattern for all remaining product areas.

Do not begin unrelated Phase 2+ integration.

## A. Import approved Command Center

Bring the approved Astro Command Center into:

```text
apps/console
```

Preserve the approved UI and route hierarchy.

Do not redesign unrelated screens.

Align monorepo dependencies/tooling only as needed.

Do not preserve fixture-backed production behavior.

## B. Workspace/CI integration

Add `apps/console` to the npm workspace.

Create root scripts/CI needed for:

- format
- lint
- typecheck
- Astro check
- unit
- build
- Playwright
- axe

Keep `apps/web` gates running.

## C. Astro SSR runtime

Configure the Phase 0-approved Vercel SSR runtime.

Authenticated routes must not prerender.

Use private/no-store caching where required.

## D. Auth/session/MFA

Implement the approved Supabase SSR architecture.

Prove:

- sign in
- sign out
- refresh
- expiry
- concurrent refresh
- MFA/AAL2
- invalid/valid TOTP
- redirect after step-up
- chunked cookies

Do not expose raw tokens to page scripts.

## E. Same-origin server endpoints

Implement explicit BFF routes required by this slice.

No generic proxy.

Enforce:

- fixed upstream
- method/path allowlist
- timeout
- request size
- origin/CSRF controls
- header stripping
- correlation propagation
- idempotency propagation where required
- token non-logging

## F. Generated transport contracts

Implement the Phase 0-approved OpenAPI TypeScript generation.

Commit generated types.

Add CI stale-contract failure.

Build tested adapters from transport types to UI view models.

## G. Client context/routing

Implement slug -> canonical org UUID resolution.

All domain/API operations use UUID after resolution.

Implement server-side coarse route guards.

Use backend capability/permission data for actions.

## H. OpportunityView

Implement the canonical read projection.

Approved classifications:

- Issue
- Growth Opportunity
- Optimization
- Data & Tracking

Do not create a duplicate write model.

Use canonical source IDs and domain actions.

## I. AttentionView

Implement operational attention without collapsing workflow/automation records.

Use only verified attention states from current contracts.

Automations remain first-class elsewhere.

## J. Canonical Opportunity detail

All Opportunity entry points must resolve to the same canonical detail experience.

Show verified available information including, as applicable:

- classification
- priority
- why discovered
- why it matters
- evidence
- metrics
- source
- detection date/period
- page attribution
- effort
- next action
- current recommendation revision
- execution state

Do not invent missing fields.

## K. Recommendation and quality review

Wire the current merged backend revision/change-set contract.

For site-change proposals, expose a high-quality review UI showing, as supported:

- current value
- proposed value
- rationale
- target page
- target field
- protected query/location/year signals
- deterministic validation state
- repository-current-value verification
- typed blocker states

Do not recreate quality logic in the frontend.

## L. Revise/edit

Wire the canonical revise endpoint.

Editing creates a new audited revision.

Do not mutate an approved revision in place.

The exact revised change set is what approval binds.

## M. Approval

Use canonical backend approval.

Do not introduce extra approval gates.

## N. Workflow/execution state

Show authoritative async state.

Do not infer success before backend reconciliation.

## O. PR/build/deploy/live verification

Surface canonical backend state for:

- mapping
- PR URL
- build gate
- checks
- merge
- deploy
- live read-back
- observed mismatch
- blocked code

Do not implement GitHub/Vercel orchestration in Astro.

## P. Correlation/causation

Verify/propagate correlation through the entire slice.

Add causation where the Phase 0 contract identified a gap.

## Q. Fixtures

Remove fixture imports from all production paths implemented by this slice.

Add hard lint/module-boundary enforcement.

## R. Required acceptance journeys

At minimum prove in staging:

1. authenticated operator loads client Opportunities
2. Opportunity evidence loads from staging API
3. Attention reflects authoritative state
4. recommendation loads
5. deterministic quality results display
6. operator revises proposal
7. new audited revision appears
8. operator approves exact revision
9. workflow is queued and shown
10. worker executes
11. staging GitHub PR opens only in approved test repo
12. build gate state appears
13. merge/deploy path completes according to staging contract
14. live verification appears
15. typed failure/retry/blocker states render correctly
16. tenant isolation is proven
17. unauthorized action is rejected by backend
18. cross-tenant cache leakage test passes

## S. Quality gates

Run the full applicable suite:

- format
- lint
- TypeScript
- Astro check
- console unit tests
- affected backend tests
- build
- browser
- axe
- auth
- MFA
- CSRF
- tenant isolation
- cache isolation
- OpenAPI drift
- fixture-boundary
- migration checks if schema changed
- vulnerability audits
- existing `apps/web` tests

Do not claim tests not run.

## Required outputs

Create/update:

```text
docs/implementation/command-center/PHASE_01_ACCEPTANCE.md
docs/implementation/command-center/DECISION_LOG.md
```

Document:

- exact implementation
- API contracts used/added
- view models/adapters
- tests run
- staging acceptance
- known gaps
- Phase 2 readiness

## Definition of done

Phase 1 is complete only when the entire reference slice works in staging, end to end, without fixture production paths, frontend business logic, duplicate backend authority, or regression to `apps/web`.

Open one coherent PR.
Do not begin Phase 2.
Do not merge automatically.
