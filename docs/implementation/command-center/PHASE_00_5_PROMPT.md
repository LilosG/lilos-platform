# Phase 0.5 — Safe Integration Environment

## Governing scope

Repository:

`LilosG/lilos-platform`

This prompt REPLACES the earlier Phase 0.5 prompt for execution.

Authority, in order:

1. current merged `main`
2. repository `AGENTS.md` / `CLAUDE.md`
3. `docs/implementation/command-center/MASTER_PLAN.md`
4. merged `PHASE_00_INTEGRATION_CONTRACT.md`
5. merged `ACCEPTANCE_MATRIX.md`
6. merged `DECISION_LOG.md`
7. this prompt

Do not reopen Phase 0 architecture unless current merged code directly contradicts a required implementation assumption.

---

# Objective

Build the isolated staging/test foundation required for Phase 1.

Phase 0.5 is complete when LILOs has a safe non-production environment and test-provider boundary that can support the new console without risking production clients.

This phase is NOT:

- another architecture audit
- another repository-wide discovery exercise
- a full-platform QA pass
- a production acceptance pass
- a UI migration phase
- a reason to debug unrelated baseline failures
- a reason to redesign existing backend systems

Do not create `apps/console` product screens in this phase.

---

# Execution discipline — mandatory

## One-pass discovery only

At the start, inspect only the current files/contracts directly required by this phase.

Do not recursively re-audit the repository.

Do not repeat Phase 0 discovery.

Do not search for "more things to improve."

If a required fact is already documented in the merged Phase 0 artifacts and current code has not contradicted it, use it.

## No broad validation loops

During implementation:

- run targeted tests for code you change
- run targeted configuration checks for infrastructure you change
- run targeted security/isolation tests for boundaries you change

At the END of the phase, run the required final gates ONCE.

If an unrelated/pre-existing test fails:

1. confirm it once
2. determine whether your changes caused it
3. if not caused by this phase and it does not block the phase, record it and continue
4. do not debug it
5. do not rerun the entire suite repeatedly

Do not chase unrelated browser failures.
Do not chase unrelated production-preflight failures.
Do not run production acceptance.
Do not repeatedly rerun full Python or browser suites.

## Owner-action handling

Do not stop at the first owner dependency.

At the beginning of the phase, produce ONE consolidated owner-action list from the merged Phase 0 artifacts.

Then continue every implementation task that is not blocked by those owner actions.

Only stop a specific subtask when it truly requires:

- billing approval
- account-owner authorization
- DNS ownership
- OAuth consent
- unavailable secret
- external resource creation the agent is not authorized to perform

Do not ask the owner multiple times for separate routine approvals.

At completion, report one consolidated remaining owner-action list.

---

# Starting state

Start from current merged `main`.

Create/use exactly one feature branch:

`command-center/phase-0-5`

Do not create extra branches for subparts of this phase.

Before editing:

```bash
git switch main
git pull --ff-only origin main
git status
git switch -c command-center/phase-0-5
```

If the branch already exists because work is being resumed, verify it and continue; do not create a second branch.

---

# MUST COMPLETE

## 1. Reconcile staging deployment configuration with current main

Modernize the existing staging deployment definition from the merged Phase 0 findings.

The staging backend topology must match the approved architecture:

- staging API
- staging worker
- staging scheduler
- staging Hermes

Do not preserve the stale staging branch reference found in Phase 0.

Do not create a second workflow engine.

Do not create a second scheduler model.

Do not create an unnecessary Render Postgres database if the approved staging database is the separate staging Supabase Postgres project.

All staging service configuration must be fail-closed and use staging-only environment variables.

No production database URL, production Supabase issuer, production encryption key, production OAuth refresh token, or production GitHub credential may be used.

If actual external resources cannot be provisioned because owner access/billing is required, complete and validate the repository configuration and mark only the external provisioning step as `OWNER ACTION REQUIRED`.

## 2. Define and enforce environment isolation in code/config

Implement configuration validation sufficient to prevent:

- Preview -> production API
- Preview -> production Supabase
- staging -> production database
- fixture provider in production
- staging GitHub writes to non-allowlisted repositories
- staging Google/GBP writes

The configuration must fail closed.

Do not rely on naming conventions alone.

Add targeted automated tests for these negative cases.

## 3. Provider fixture adapters

Implement non-production provider fixtures through the EXISTING canonical adapter seams identified in Phase 0.

At minimum cover the approved provider boundaries for:

- Search Console
- GA4
- GBP

Do not put `if environment == "staging"` logic inside product services.

Select adapters centrally through dependency/composition configuration.

Production startup/configuration must reject fixture providers.

Required deterministic scenarios:

- healthy
- expired/reconnect required
- rate-limited
- provider unavailable/timeout
- partial response
- missing mapping

Use canonical normalized return/error contracts.

Do not create a parallel provider abstraction.

## 4. Shared adapter contract tests

Create one shared contract-test approach that both:

- fixture adapters
- real production adapters using sanitized recorded responses

must satisfy.

CI must remain deterministic.

Do not call live Google APIs from ordinary CI.

Recorded payloads must contain no credentials, tokens, or client PII.

Do not spend this phase building an elaborate recording framework if a small deterministic fixture layer is sufficient.

## 5. Provider write isolation

The Phase 0 contract confirmed the existing global provider-write switch is not sufficient for staging's required behavior.

Implement the smallest canonical improvement that provides:

- global fail-closed behavior remains
- Google/GBP writes denied in staging
- GitHub writes allowed only for one explicit test repository/installation/path scope

Use existing provider/publishing boundaries.

Do not build a new policy engine.

Do not expose write controls to the browser.

Add negative tests for:

- wrong repo
- wrong owner
- wrong installation
- disallowed path
- Google/GBP write attempt
- fixture provider in production

## 6. Synthetic staging seed mechanism

Implement an idempotent staging-only seed path through canonical services/contracts.

Do not seed by copying production rows.

Do not copy production identifiers.

Do not copy production OAuth tokens.

Seed only the representative shapes required by Phase 0:

- hospitality single-location
- home-service / SAB
- multi-location
- healthy integration state
- reconnect-required state
- partial/unavailable provider state
- publishing-enabled test organization

Keep seed data deterministic.

The seed mechanism must refuse production execution.

Do not overbuild sample content beyond what Phase 1 acceptance needs.

## 7. Generated/test environment prerequisites

Prepare the repository-side configuration needed for:

- staging Supabase Auth + Postgres
- staging Render services
- Vercel protected Preview environment
- stable `console-staging.lilosgrowth.com`
- dedicated GitHub test repository
- independent staging OAuth credentials

Where external creation is owner-controlled, do not fabricate IDs/secrets and do not block unrelated implementation.

Create a concise owner-action checklist with the exact external values/actions still required.

## 8. Live Google smoke path

Implement only the code/config/schedule path required for a later read-only smoke test using independently authorized staging credentials and LILOs-owned properties.

No production refresh-token copying.

No Google/GBP writes.

Do not attempt live OAuth if owner authorization is unavailable.

Do not run live production Google acceptance in this phase unless the staging credentials are already explicitly available and authorized.

A missing owner authorization is not a reason to stop the rest of Phase 0.5.

## 9. Staging GitHub test publishing path

Prepare the canonical staging publishing configuration for exactly one dedicated test repository.

If the repository/App installation does not yet exist, complete all code/config/tests that do not require it, then mark the final connection as owner action.

Do not use a client repo.

Do not use the production LILOs Growth repo as the staging write target.

## 10. LILOs Growth production-canary readiness

Do NOT perform the production canary in Phase 0.5.

Only complete the approved setup work that is safe and explicitly authorized.

The production canary remains a later acceptance step.

If adding the dedicated canary source page/reset harness requires a separate repository PR or explicit owner approval, record that as a separate owner action rather than delaying unrelated staging work.

Do not modify normal LILOs Growth business pages.

Do not create the defect on production in this phase.

---

# MUST NOT DO

Do not:

- create `apps/console` product implementation
- migrate Command Center screens
- debug the known standalone Opportunity-row baseline issue
- rerun its browser failure repeatedly
- re-audit every FastAPI route
- re-audit every existing frontend screen
- rerun broad production-preflight loops
- query production data merely to "double check" Phase 0
- make client writes
- test against client repositories
- copy production data into staging
- copy production OAuth/refresh tokens into staging
- add a second provider framework
- add a second workflow engine
- add a second scheduler
- add a generic policy engine
- redesign auth
- redesign the Command Center
- upgrade unrelated dependencies
- perform opportunistic cleanup
- modify unrelated product code
- introduce new phases
- begin Phase 1
- merge automatically

If you find something unrelated that would be "nice to fix", record it only if relevant and continue.

---

# Required targeted validation during implementation

Run only the tests/checks associated with changed areas while developing.

Examples:

- staging config validation
- provider adapter contract tests
- fixture-production rejection tests
- provider-write isolation tests
- synthetic seed idempotency/production-refusal tests
- secrets/config tests
- migration tests only if this phase actually adds a migration

Do not run the complete repository test matrix after every change.

---

# Final gates — run once after implementation is complete

Run the relevant repository-required final checks once.

At minimum, if affected by the changes:

- format
- lint
- typecheck
- targeted backend test modules for changed code
- staging/render config check
- secrets check
- dependency audit if dependencies changed
- migration check if schema changed
- `git diff --check`

Do not run browser suites if no browser/application UI code changed.

Do not run the standalone Command Center browser suite in Phase 0.5.

Do not run production-preflight against missing production secrets merely to generate a known fail-closed result.

If repository CI later runs broader gates automatically, let CI run them; do not preemptively duplicate them locally unless required by repository instructions.

---

# Required deliverable

Create/update:

`docs/implementation/command-center/PHASE_00_5_ACCEPTANCE.md`

Update:

`docs/implementation/command-center/DECISION_LOG.md`

The acceptance document must be concise and implementation-focused.

It must record:

- exact files changed
- exact staging configuration implemented
- fixture adapters implemented
- contract tests implemented
- provider-write isolation implemented
- seed mechanism implemented
- tests actually run
- external resources actually created/connected
- external resources not created
- one consolidated owner-action list
- actual recurring cost introduced, if any
- Phase 1 readiness

Do not recreate the Phase 0 architecture document.

---

# STOP CONDITION

Phase 0.5 is complete when:

1. all repository-side staging/isolation/provider/seed work that can be completed without owner-controlled external actions is complete
2. targeted tests pass
3. external owner dependencies are reduced to one explicit checklist
4. no production/client assets were mutated
5. Phase 1 can start as soon as the remaining external prerequisites required by Phase 1 are satisfied

If some external resource is still blocked, classify Phase 1 readiness precisely:

- `READY`
- `READY WITH OWNER ACTIONS BEFORE LIVE STAGING`
- `BLOCKED`

Do not mark the whole phase blocked merely because one future smoke/canary connection is unavailable if Phase 1 implementation can safely proceed against synthetic staging.

---

# Git / PR workflow

When the phase implementation is complete:

```bash
git status
git diff --check
git diff --stat
```

Review the complete diff.

Commit the complete Phase 0.5 scope on the one phase branch.

Push:

```bash
git push -u origin command-center/phase-0-5
```

Open one PR against `main`.

Do not merge it.

Do not start Phase 1.

---

# Completion report

Report only:

- branch
- commit SHA
- PR link
- exact files changed
- implementation completed
- targeted tests/checks run and results
- external resources actually connected
- single consolidated owner-action checklist
- actual/estimated incremental staging cost
- Phase 1 readiness classification
- any true blocker caused by this phase

Do not include a long narrative of exploratory commands.
Do not include unrelated baseline failures unless they directly affect Phase 0.5.
Do not begin Phase 1.
