# ADR 0005: Location foundation policies

- Status: Accepted
- Date: 2026-08-02
- Decision owners: LILOs platform architecture

## Context

The master specification establishes locations beneath the organization tenant boundary but leaves several initial enforcement details open. PHASE-02-TASK-02 requires explicit classifications, lifecycle rules, parent-state restrictions, address semantics, and primary-location behavior before persistence can be safely implemented.

## Decision

Initial location types are `physical`, `service_area`, `hybrid`, and `virtual`. `department` is deferred until its parent relationship and inheritance rules exist. Statuses are `setup_required`, `active`, `paused`, `closed_temporarily`, `closed_permanently`, and `archived`.

Lifecycle transitions are:

- `setup_required` → `active` or `archived`
- `active` → `paused`, `closed_temporarily`, or `closed_permanently`
- `paused` → `active`, `closed_temporarily`, `closed_permanently`, or `archived`
- `closed_temporarily` → `active`, `paused`, or `closed_permanently`
- `closed_permanently` → `archived`
- `archived` is terminal

Every transition requires the expected version and increments it once. Closed-permanently locations cannot reopen, and active locations cannot archive directly.

Organizations in `prospect` or `onboarding` may create setup-required locations and read, but cannot activate or reopen them. Active organizations allow all approved operations. Paused organizations may create and read, and may progress toward pause or closure but cannot activate/reopen. Suspended and archived organizations are read-only. Offboarding organizations permit only eligible progression to permanent closure or archival.

Physical locations require a complete street address. Service-area locations require a service-area description and country; their core street-address fields are all-or-none. Hybrid locations require both. Virtual locations require a website and country and forbid address, coordinate, and service-area fields.

Slugs use the established normalized 3–63 character lowercase ASCII convention, are unique within an organization, immutable, and never released on archival. A partial unique PostgreSQL index permits zero or one `is_primary` location per organization. Virtual locations may be primary; archival does not reassign primary status.

All persistence access is organization-scoped. `audit_events.location_id` is nullable and references `locations.id` with `ON DELETE RESTRICT`. Location mutation and audit creation share the caller-owned transaction.

Temporary location routes retain the existing internal-route guard: unregistered by default, explicitly usable only in local/test, and rejected in development, staging, and production. They are not an authentication or authorization mechanism.

## Consequences

The database and service layer can enforce an explicit initial contract without inventing department hierarchy or primary reassignment. Application scoping is testable now; authorization and PostgreSQL RLS remain later work. Production database roles for non-deletion and other least-privilege controls also remain deployment work.
