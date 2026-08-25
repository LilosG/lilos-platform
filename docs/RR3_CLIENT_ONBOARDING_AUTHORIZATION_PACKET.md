# RR-3 — Client Onboarding Authorization Boundary

## Goal
Close the P0 authorization defect in the client onboarding API without attempting the full onboarding sequence while PR47 is still defining Automation Defaults/readiness contracts.

## Baseline
Branch from PR46 accepted commit `a91e64367810d7d45524b472a3007a6ba9fe1cb5`.

## Confirmed root cause
`/api/v1/client/onboarding` exposes organization creation, state and activation, but authorization is based too broadly on active membership. A client member/viewer can reach activation semantics that should require an explicit decision. The existing `/onboarding` web page is platform-admin-only and there is no complete client step-completion UI; that broader journey is intentionally not part of RR-3.

## Ownership
- `apps/api/app/routes/client_onboarding.py`
- client-onboarding-specific authorization helper/dependency only if required and kept outside shared PR47 surfaces
- focused tests under `tests/python/onboarding/**`
- release-ledger evidence for this packet only

## Exclusions
Do not modify:
- workflow/automation execution
- Hermes/AI
- integrations or product services
- full onboarding readiness/service sequence
- `apps/web/src/pages/onboarding.astro`
- platform administration beyond a test fixture if absolutely required

## Required behavior
1. Every client onboarding operation must have an explicit role/permission authorization decision.
2. Organization creation, state read, step mutation if present, and activation must not all inherit the same broad membership check.
3. Viewer/member activation must be denied unless the canonical access model explicitly grants an activation capability.
4. Client owner/authorized role behavior must be explicit and covered by tests.
5. Tenant isolation and organization ownership must be enforced on every read/mutation.
6. Preserve assurance/AAL requirements where the existing authorization framework requires them; activation should not become weaker than comparable privileged lifecycle mutations.
7. Cross-tenant and suspended/inactive membership behavior must fail closed without existence disclosure.
8. Do not create a second onboarding engine or responsibility model.

## Acceptance matrix
Tests must cover at minimum:
- authorized client owner can read own onboarding state;
- client viewer can read only if current contract permits, but cannot activate;
- ordinary client member cannot activate unless explicitly entitled by canonical role policy;
- suspended member denied;
- user from another organization denied;
- wrong organization ID does not disclose records;
- platform administrator behavior remains valid;
- assurance/AAL behavior is deterministic;
- activation still uses the canonical onboarding service and audit path.

## Deferred by design
The full Business -> Locations -> Products -> Integrations -> Resource Mapping -> Configuration -> Automation Defaults -> Readiness -> Activate sequence remains RR-5 after PR47, because Automation Defaults/readiness contracts may be touched by the Hermes operationalization work.

## Validation
Focused onboarding/API authorization tests, Ruff and mypy first. Then one integrated repository validation. Stop on unrelated failure. Commit/push only when green; do not merge.