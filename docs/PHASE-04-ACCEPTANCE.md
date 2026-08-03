# Phase 4 acceptance

## Objective

Phase 4 establishes governed services, business facts, immutable product/configuration catalogs,
entitlements, computed readiness, effective configuration, policy categories, feature flags,
runtime controls, onboarding blockers, and non-destructive offboarding plans.

## Persistence and isolation

Migration `20260803_0001` descends from `20260802_0007`. Tenant records carry `organization_id`;
location ownership uses composite restrictive foreign keys. Stable keys and released content have
database immutability triggers. All foreign keys use `ON DELETE RESTRICT`; downgrade removes only
Phase 4 structures and preserves Phase 1–3 data and audit history.

## Acceptance checklist

- [x] Entitlement does not falsely imply readiness or authorization.
- [x] Activation requires fresh readiness.
- [x] Business facts are approved, versioned, effective-dated, and conflict-aware.
- [x] Configuration is schema-validated, inherited, historical, and source-explained.
- [x] Policies are versioned declarative assets; no workflow/notification executes.
- [x] Flags never grant access; restrictive runtime controls win.
- [x] Onboarding blockers are typed and visible.
- [x] Offboarding is resumable, audited, non-destructive, and evidence-based.
- [x] APIs enforce fixed permissions/AAL and tenant isolation.
- [x] Seeds are explicit, atomic, idempotent, and mismatch detecting.
- [x] Governing documents remain unchanged.

## Validation, deferral, and status

Focused PostgreSQL validation passed 15 Phase 4 tests and 57 Phase 3 security regressions. The
repository check passed 208 Python tests with 119 expected integration skips, one frontend test,
all static checks, the production build, and secret scanning; the complete PostgreSQL-backed suite
passed all 327 tests. PostgreSQL 17 completed clean
base-to-head, no-drift, catalog seed/idempotency/mismatch, cross-tenant rejection, downgrade, and
re-upgrade validation. Final totals are recorded in `IMPLEMENTATION-STATUS.md`. Deferred: Phase 5 workflows/workers/scheduler, integrations,
approval execution, notifications, RLS, billing synchronization, product modules, frontend, and AI.
The upstream Starlette/httpx warning remains unchanged and unsuppressed.

Phase 4 implementation and local acceptance are complete; hosted CI evidence is recorded after the
final commit and push.
