# Phase 1 — Console Foundation + Opportunities/Attention Reference Slice

## Authority

Repository: `LilosG/lilos-platform`

Authority, in order:
1. current merged `main`
2. repository `AGENTS.md` / `CLAUDE.md`
3. `docs/implementation/command-center/MASTER_PLAN.md`
4. `PHASE_00_INTEGRATION_CONTRACT.md`
5. `ACCEPTANCE_MATRIX.md`
6. `PHASE_00_5_ACCEPTANCE.md`
7. `DECISION_LOG.md`
8. this prompt

This prompt REPLACES the earlier Phase 1 prompt.

Approved UI source: `LilosG/lilos-command-center-astro`
Approved UI baseline SHA: `d097c5255995b010f45b67a8ace90a80d00f090b`
Do not silently use a later UI commit.

## Starting condition

Phase 0 and Phase 0.5 are merged.

Phase 0.5 repository implementation is complete. External live staging is still pending owner-controlled setup. Current readiness is:

`READY WITH OWNER ACTIONS BEFORE LIVE STAGING`

Therefore:
- begin Phase 1 repository implementation now
- do not stop the whole phase because DNS/OAuth/Supabase/Render/Vercel/GitHub-test-repo setup is pending
- use the merged Phase 0.5 synthetic/fixture/provider boundaries for deterministic acceptance
- do not claim live staging acceptance until those external resources actually exist
- mark only the specific live acceptance items as pending owner action

## Objective

Create `apps/console` and complete one production-grade reference slice:

```text
authenticated console
-> organization/client context
-> OpportunityView / AttentionView
-> canonical Opportunity detail
-> evidence
-> recommendation
-> deterministic validation
-> revise/edit
-> exact approval
-> workflow/run state
-> governed publication state
-> PR/build/deploy/live-verification state
```

This is an implementation phase, not another architecture audit.

## Execution discipline — mandatory

### One-pass verification only
At the start, verify current branch/base, read the governing files, verify the exact approved UI SHA, and inspect only code directly required by Phase 1.

Do not repeat Phase 0 inventory.
Do not re-audit all prototype routes.
Do not re-audit every backend product.
Do not re-open Phase 0.5 provider/staging design.
If merged contracts already define the architecture and current code does not contradict them, implement them.

### No broad debugging loops
During development run targeted tests for changed code and focused browser tests for changed console journeys.
At the end run the required final gates once.

If an unrelated pre-existing failure appears:
1. determine whether Phase 1 caused it
2. if not caused by Phase 1 and not blocking this slice, record it
3. do not debug it
4. do not repeatedly rerun broad suites

Do not chase the standalone reference-repo Opportunity browser baseline failure unless the imported console reproduces it in a Phase 1 acceptance journey.

### Owner actions
Do not stop at the first external dependency. Continue all repository-side work that can be completed safely. External resources are acceptance dependencies, not automatic implementation blockers.

## Branch

Use exactly one branch: `command-center/phase-1`

Do not create sub-branches.

# MUST COMPLETE

## 1. Create `apps/console`
Import the approved Command Center at exact SHA `d097c5255995b010f45b67a8ace90a80d00f090b` into `apps/console`.

Preserve approved information architecture, route hierarchy, components, and visual behavior. Do not redesign unrelated screens.

Do not copy `.git`, build output, `node_modules`, or standalone deployment history.

Record the imported SHA in Phase 1 acceptance.

A missing published tag does NOT block import because the immutable commit SHA is authoritative.

## 2. Monorepo/workspace integration
Integrate `apps/console` into existing workspace/tooling for install, format, lint, typecheck, Astro check, unit tests, build, Playwright, and axe.

Keep existing `apps/web` gates intact. Do not retire `apps/web`.

## 3. Astro SSR runtime
Configure the approved Astro SSR/Vercel runtime.

Requirements:
- authenticated tenant pages are SSR
- no authenticated tenant prerendering
- authenticated responses use `Cache-Control: private, no-store`
- no process-global user/session/tenant state
- merged Phase 0.5 console prerequisite validation is actually invoked where appropriate

## 4. Supabase SSR auth/MFA
Implement server-mediated Supabase auth preserving existing valid behavior:
- sign in/out
- refresh/expiry
- MFA/AAL2
- verified-factor reuse
- abandoned unverified enrollment cleanup
- valid/invalid TOTP
- safe post-MFA return
- cookie chunk cleanup

Requirements:
- host-only secure cookies
- HttpOnly session material
- no raw access/refresh token in page JS
- request-scoped Supabase server client
- FastAPI remains final authz/AAL/action authority
- focused tests for concurrent refresh/stale-cookie response ordering

## 5. Same-origin BFF
Implement only explicit server endpoints required by this slice.

No generic proxy.

Enforce:
- fixed FastAPI upstream
- literal route/method allowlist
- validated UUID/path/query/body inputs
- request-size limits
- bounded timeouts
- no upstream redirects
- unsafe/hop-by-hop header stripping
- server-side Bearer attachment
- correlation propagation
- idempotency propagation only where backend supports it
- token/cookie/TOTP redaction

Business logic stays in FastAPI.

## 6. CSRF/host/cache isolation
Implement expected Origin/host checks, session-bound CSRF, safe return targets, trusted preview-host validation, and private/no-store authenticated responses.

Add cross-tenant tests proving tenant A data cannot be served to tenant B through SSR, loaders, BFF responses, or caching.

## 7. OpenAPI transport contracts
Implement deterministic FastAPI OpenAPI export and generated TypeScript transport types:

```text
FastAPI/Pydantic -> OpenAPI -> generated TS transport -> tested adapters -> UI view models
```

Commit generated artifacts and add CI drift detection.

Do not expose raw transport schemas throughout the UI.

Where Phase 1 responses are too generic for safe typing, add the smallest additive typed backend read DTO needed while preserving `apps/web` compatibility.

## 8. Client context and slug -> UUID
Implement:

```text
client slug -> authorized canonical organization -> UUID -> UUID-only downstream API calls
```

No sample numeric client identity. No display-name authority. Backend remains final permission authority.

## 9. `OpportunityView`
Implement the additive canonical read projection from Phase 0.

Approved classifications only:
- Issue
- Growth Opportunity
- Optimization
- Data & Tracking

Do not create a universal Opportunity write model.
Use stable namespaced source IDs and canonical underlying actions.
Implement only sources required for this reference slice plus the minimal extensible projection framework.

## 10. `AttentionView`
Implement operational attention separately from Opportunity.

Use canonical typed states such as reconnect required, missing mapping, waiting approval, workflow failure, retry scheduled, publication/build blocked, and other verified states.

Do not create local dismiss-as-resolved authority.
Do not collapse WorkflowRun, Job, Schedule, AgentRun, ContentPublication, or provider records into a new write system.

## 11. Remove fixture authority from production paths
Imported prototype fixtures may remain for isolated tests only.

Production console code must not import prototype fixture/sample-session modules.
Add module-boundary/lint enforcement.
No silent fixture fallback.
No source -> explicit unavailable/empty state.
Preserve null/stale/partial/unavailable distinctions.

## 12. Canonical Opportunity list/detail
All Phase 1 Opportunity entry points resolve to one canonical detail experience.

Render authoritative values only, including as available:
- classification
- priority
- source
- why discovered
- why it matters
- evidence
- period/freshness/quality
- page attribution
- effort
- expected gain only when authoritative/hypothesis-backed
- next action
- recommendation revision
- workflow/publication state

## 13. Recommendation and deterministic quality state
Wire the current merged SEO recommendation/change-set contract.

Show backend-authoritative current/proposed values, rationale, target page/field, protected query/location/year signals, deterministic quality result, repository-current-value verification, and typed blockers.

Do not duplicate quality logic in Astro.

## 14. Revise/edit
Wire the canonical revise endpoint. Editing creates a new audited revision. Do not mutate approved/superseded historical revisions in place.

## 15. Approval
Use canonical backend approval only. Do not add extra frontend approval systems or blanket approval gates.

## 16. Workflow/run/publication state
Render authoritative durable states. Do not infer completion from request acceptance.
Preserve queued/running/waiting/waiting-approval/retry/blocked/failed/completed/verified/superseded/withdrawn/reconciliation distinctions where applicable.

## 17. GitHub/build/deploy/live-verification state
The console surfaces canonical backend state; it does not orchestrate GitHub/Vercel directly.

Show available mapping, PR URL/state, checks/build gate, merge/deployment state, live read-back, mismatch/blocker, verification state.

If the external dedicated staging GitHub repo/App is not yet connected, complete repository integration and deterministic tests, then mark live publication acceptance pending owner action.

Do not substitute a client repo or production LILOs Growth repo.

## 18. Correlation/causation
Propagate existing correlation through browser -> console -> FastAPI -> workflow/job -> Hermes where used -> publication.
Add only missing causation references actually required by this slice.

# ACCEPTANCE — TWO LEVELS

## A. Repository/synthetic acceptance — REQUIRED FOR THIS PR
Prove deterministically:
1. console builds in monorepo
2. SSR auth/session path works
3. MFA/AAL2 behavior is preserved
4. BFF allowlist/security works
5. CSRF/origin/host protections work
6. tenant/cache isolation works
7. OpenAPI generation/drift works
8. slug resolves once to org UUID
9. OpportunityView uses canonical source IDs
10. AttentionView uses canonical operational states
11. Opportunity detail renders authoritative evidence
12. recommendation quality state renders from backend
13. revise creates a new revision
14. approval binds exact revision
15. workflow/run state displays from canonical records
16. publication/PR/build/deploy/live-verification states render from canonical contracts
17. fixture imports are blocked from production paths
18. unauthorized/cross-tenant actions are rejected
19. existing `apps/web` remains functional

Use merged Phase 0.5 fixtures/synthetic seed/provider boundaries where external services are unavailable.

## B. Live staging acceptance — REQUIRED BEFORE PRODUCTION ROLLOUT, NOT A REASON TO BLOCK REPOSITORY IMPLEMENTATION
When owner-controlled staging resources exist, additionally prove:
1. protected staging console login
2. staging Supabase Auth/Postgres isolation
3. synthetic staging org access
4. independent Google read smoke
5. dedicated GitHub test-repo publication
6. real PR/check/deploy/live verification through staging test target
7. live cookie/host/protection behavior
8. measured staging performance

If unavailable because owner actions remain, record:

`PENDING OWNER ACTION — LIVE STAGING ACCEPTANCE`

Do not falsely mark these passed and do not block the repository implementation solely because they are pending.

# MUST NOT DO

Do not:
- repeat Phase 0 discovery
- repeat Phase 0.5 design
- provision paid resources without explicit approval
- use production/client assets for staging
- run the production canary
- modify normal LILOs Growth business pages
- copy production OAuth tokens into staging
- add a generic proxy
- move permission logic into Astro
- create duplicate workflow/job/publication systems
- create a universal Opportunity write model
- invent missing metrics
- treat missing as zero
- redesign unrelated Command Center screens
- migrate Phase 2+ product areas
- perform unrelated dependency upgrades/cleanup
- repeatedly run broad suites during development
- debug unrelated pre-existing failures
- begin Phase 2
- merge automatically

# Validation discipline

During development run targeted tests only for changed areas.

At the end run applicable required gates once:
- format
- lint
- TypeScript
- Astro check
- console unit tests
- affected backend tests
- console build
- console browser tests required by repo CI
- axe
- auth/MFA
- CSRF
- tenant/cache isolation
- OpenAPI drift
- fixture-boundary
- migration check only if schema changed
- dependency/vulnerability checks if dependencies changed
- existing `apps/web` tests
- `git diff --check`

If CI runs broader gates, let CI run them. Do not duplicate them repeatedly locally.

# Required outputs

Create/update:

```text
docs/implementation/command-center/PHASE_01_ACCEPTANCE.md
docs/implementation/command-center/DECISION_LOG.md
```

Separate clearly:
- repository/synthetic acceptance
- live staging acceptance
- owner actions
- tests actually run
- tests not run
- exact files changed
- exact imported UI SHA
- API/read-model contracts added
- auth/security changes
- known gaps
- Phase 2 readiness

Do not rewrite Phase 0 architecture documents.

# STOP CONDITION

Phase 1 repository implementation is complete when:
1. `apps/console` exists and builds
2. auth/SSR/BFF/security foundations are implemented
3. generated contracts/adapters are implemented
4. OpportunityView/AttentionView are implemented
5. canonical Opportunity detail/revise/approve/workflow/publication-state slice works under deterministic/synthetic acceptance
6. production fixture imports are blocked
7. required final gates pass
8. `apps/web` remains intact
9. external live staging items are passed or explicitly pending owner actions

Final readiness must be one of:
- `READY FOR LIVE STAGING ACCEPTANCE`
- `READY FOR PHASE 2 WITH LIVE STAGING ACCEPTANCE PENDING`
- `BLOCKED`

Do not mark Phase 1 blocked solely because owner-controlled live staging resources are not yet provisioned if repository implementation and synthetic acceptance are complete.

# Git / PR workflow

At completion:

```bash
git status
git diff --check
git diff --stat
```

Review the complete diff, commit the complete Phase 1 scope on `command-center/phase-1`, push it, and open one PR against `main`.

Do not merge it.
Do not begin Phase 2.

# Completion report

Report only:
- branch
- commit SHA
- PR link
- exact files changed
- exact imported UI SHA
- repository implementation completed
- repository/synthetic acceptance results
- live staging acceptance results or pending owner actions
- final gates/results
- one consolidated owner-action checklist
- Phase 2 readiness classification
- true blockers caused by Phase 1

Do not include a long exploratory command log.
Do not begin Phase 2.
