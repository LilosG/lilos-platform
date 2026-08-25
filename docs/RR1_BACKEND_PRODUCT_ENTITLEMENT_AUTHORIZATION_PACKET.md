# RR-1 — Backend Product-Entitlement Authorization

## Goal
Close the P0 security gap where backend authorization evaluates role permissions without enforcing effective product entitlement state. Frontend navigation hiding is not an authorization control.

## Baseline
Branch from PR46 accepted commit `a91e64367810d7d45524b472a3007a6ba9fe1cb5`.

## Confirmed root cause
The authorization service checks user, organization, membership, location, assurance, roles, permissions and explicit denies, but product entitlement state is not part of the decision. Organization member/viewer roles can therefore hold read permissions for products that are not actually entitled. Direct API calls can bypass hidden navigation.

## Ownership
Only these surfaces may be changed unless a directly required authorization-local test fixture requires adjustment:
- `apps/api/app/authorization/contracts.py`
- `apps/api/app/authorization/dependencies.py`
- `apps/api/app/authorization/enums.py`
- `apps/api/app/authorization/service.py`
- a new module under `apps/api/app/authorization/` if needed
- `tests/python/authorization/**`
- release-ledger evidence for this packet only

## Explicit exclusions
Do not modify product routes, product services, execution/workflow files, Hermes/AI code, shared agent UI, onboarding, integrations, leads, GBP, SEO, Content, Reviews or Insights implementation.

## Required behavior
1. Authorization must enforce effective entitlement for product-scoped permissions server-side.
2. Disabled, suspended, expired, archived or otherwise non-effective entitlements must deny product access even when a role includes the product permission.
3. Product entitlement evaluation must be organization-scoped and, where the existing entitlement model supports it, location-aware.
4. Platform-administrator semantics must be explicit; do not accidentally remove legitimate platform-admin access.
5. Permission-to-product mapping must be centralized and deterministic. Do not infer product from arbitrary route strings.
6. Non-product permissions must remain unaffected.
7. Existing role, AAL, explicit-deny, membership and location checks remain authoritative and conjunctive.
8. Denials must not disclose cross-tenant existence.
9. Avoid per-request N+1 entitlement lookups if the current authorization context can load effective entitlements once.

## Acceptance matrix
Negative tests must prove:
- role has `gbp.read`, org has no GBP entitlement -> denied;
- role has `seo.read`, entitlement suspended -> denied;
- role has `content.read`, entitlement archived/disabled -> denied;
- entitled product + valid role permission -> allowed;
- entitlement does not grant a permission the role does not already have;
- explicit deny still wins;
- wrong organization / wrong location still fails;
- platform-admin behavior matches existing contract;
- non-product authorization is unchanged.

## Validation
Run focused authorization tests first, then Ruff/mypy for touched backend files. If focused green, run the repository integrated validation exactly once. If the integrated run fails, diagnose the exact owner; do not change unrelated code and do not blindly rerun.

## Completion
Commit and push only when repository acceptance is green. Do not merge. Report root cause confirmation, exact mapping strategy, tests, changed files, commit SHA and any remaining live client-role/entitlement acceptance.