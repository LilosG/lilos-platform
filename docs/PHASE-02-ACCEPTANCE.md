# Phase 2 acceptance — tenant, organization, and location model

## Objective and result

Phase 2 establishes organization as the platform tenant boundary, organization-owned locations,
controlled classification and context, scoped grouping, and deterministic business-identity
resolution. The phase is accepted as complete on 2026-08-02 with no Phase 3 functionality included.

## Completed packets and commits

| Packet                   | Deliverable                              | Commit                 |
| ------------------------ | ---------------------------------------- | ---------------------- |
| PHASE-02-TASK-01-REVISED | Organization tenant boundary             | `2d2dae5`              |
| PHASE-02-TASK-02         | Organization-scoped locations            | `45c8671`              |
| PHASE-02-TASK-03         | Industry classification                  | `9f1f672`              |
| PHASE-02-TASK-04         | Organization and location profiles       | `0bc47a3`              |
| PHASE-02-TASK-05         | Organization-scoped location groups      | `37f8fb8`              |
| PHASE-02-TASK-06         | Business identity and Phase 2 acceptance | This acceptance commit |

ADR 0004 resolves the roadmap's tenant and agency terminology: organization is the technical
tenant; agency access is a future permissioned cross-organization capability, not another tenant
or workspace ownership table.

## Entities and migration sequence

Implemented Phase 2 entities are `organizations`, `locations`, `industries`,
`organization_profiles`, `location_profiles`, `location_groups`, and
`location_group_memberships`. Audit scope references organizations and locations. Business identity
is computed and has no table.

Phase 2 migrations form one deterministic chain:

1. `20260802_0001` — organizations and audit organization ownership
2. `20260802_0002` — locations and audit location ownership
3. `20260802_0003` — industries and nullable organization industry assignment
4. `20260802_0004` — organization and location profiles
5. `20260802_0005` — location groups and memberships (current head)

## Tenant boundary and isolation

- Organization is the highest ownership boundary; no `tenants` table exists.
- Every location and other tenant-owned Phase 2 record carries direct organization scope.
- Composite constraints prevent cross-organization location-profile and group membership ownership.
- Scoped repositories include organization identifiers in child-record queries.
- Cross-organization child identifiers return the same not-found behavior as absent records.
- Business identity has no global listing/search and location resolution is organization-scoped.
- Authentication, authorization, request context, and RLS are Phase 3 controls; internal routes
  remain disabled outside explicit local/test use.

## Lifecycle and concurrency guarantees

Organizations, locations, industries, profiles, and groups enforce their documented lifecycle and
parent-state rules. Archived terminal states cannot be reopened through normal services. Mutable
Phase 2 records use positive integer versions and atomic compare-and-swap operations; every
successful mutation increments exactly once and stale writes return stable conflicts. Immutable
slugs/keys additionally have PostgreSQL triggers.

Business-identity reads preserve every parent lifecycle state and never change lifecycle or
version state.

## Audit guarantees

Every Phase 2 mutation—organization and location lifecycle, industry changes/assignment, profile
creation/update, group changes, and membership changes—writes bounded audit evidence in the same
caller-owned transaction. Owning failures roll back both changes. Audit metadata excludes full
profiles, policy documents, contacts, customer data, credentials, and secrets. PostgreSQL rejects
audit update, delete, and truncate operations. Read-only business-identity resolution emits no audit
record.

## Internal route limitations

Phase 2 routes are temporary unauthenticated bootstrap surfaces. They are unregistered by default,
can be enabled only in local/test, and fail configuration validation in development, staging, and
production. They contain no bypass token and are not production-safe administration APIs.

## Explicitly deferred work

- Authentication, membership, authorization, scoped roles, Supabase Auth, and PostgreSQL RLS
- Full configuration inheritance, business facts, and cross-level list/claim resolution
- Agency permission workflows and production support access
- Products, entitlements, workflows, integrations, AI, publishing, billing, and frontend admin
- Production database roles, provisioning, deployment, monitoring, and backups

## Test coverage and acceptance criteria

Phase 2 suites cover contracts, lifecycle matrices, concurrency, ownership, cross-organization
negative access, audit atomicity, rollback, route guards, migrations, triggers, constraints, seed
idempotency, missing data, and deterministic read composition against PostgreSQL 17.

Final acceptance validation passed 250 Python tests, including 32 focused business-identity tests,
plus frontend formatting, linting, typing, Vitest, and build. PostgreSQL 17 completed clean
base-to-head upgrade, Alembic drift check, complete Phase 2 catalog inspection, downgrade to base,
re-upgrade to head, and a second no-drift check.

- [x] Organization tenant boundary and lifecycle complete
- [x] Location foundation and lifecycle complete
- [x] Industry classification and organization assignment complete
- [x] Organization and location profiles complete
- [x] Location groups and memberships complete
- [x] Business identity resolves by organization and location
- [x] Tenant-owned Phase 2 records preserve organization scope
- [x] Cross-organization negative tests pass
- [x] Mutable Phase 2 domains use optimistic concurrency
- [x] Every Phase 2 mutation uses atomic audit integration
- [x] Migration chain upgrades, downgrades, re-upgrades, and reports no drift
- [x] Internal bootstrap-route safeguards pass
- [x] Domain documentation and ADRs describe implemented and deferred behavior

## Known warning and final status

Starlette emits its existing deprecation warning for the current `httpx`-backed test client. The
locked intended dependency remains `httpx`; the warning is not suppressed and does not affect test
results.

**Phase 2 status: COMPLETE.** Phase 3 must not infer authentication or authorization from these
ownership and route-guard foundations.
