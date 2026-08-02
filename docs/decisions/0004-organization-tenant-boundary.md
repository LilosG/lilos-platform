# ADR 0004: Organization is the technical tenant boundary

- Status: Accepted
- Date: 2026-08-02
- Owners: Platform Engineering
- Related roadmap phase: Phase 2

## Context

The roadmap describes a “Platform tenant model,” while the master specification consistently names
organization as the primary tenant boundary and requires tenant-owned records to carry
`organization_id`. Interpreting the roadmap phrase as a separate entity would introduce an
unapproved ownership layer and conflict with the specification's terminology and isolation model.

## Decision

Organization is the highest-level technical tenant boundary. The platform has no separate
`tenants` table or tenant entity. “Tenant-aware” repositories, services, APIs, workflows, and tests
mean organization-scoped behavior.

Future location-scoped records carry both their location reference and direct organization
ownership when required by the master specification. Later phases will enforce organization
isolation through authenticated request context, application authorization, scoped repositories,
PostgreSQL foreign keys, Row Level Security, and negative cross-organization tests.

Audit events retain nullable `organization_id`, now constrained to the organization table. Internal
cross-organization access remains future permissioned, explicit, and audited behavior; this ADR
does not authorize a universal platform bypass.

## Consequences

- Organization slugs are stable tenant identifiers and cannot be reused or changed.
- Future tenant-owned tables reference `organization_id`; they do not reference a separate tenant.
- Locations cannot become independent tenants and must preserve organization ownership.
- Agency administration is a permissioned cross-organization capability, not another tenant tier.
- Authentication, authorization, memberships, locations, and RLS remain later roadmap work.
- A future proposal for a separate ownership tier requires a formal master-spec architecture
  revision and migration strategy.

## Alternatives considered

- Add `tenants` above organizations: rejected because it contradicts the master specification and
  would leave future ownership, RLS, and organization relationships ambiguous.
- Treat agency workspaces as tenants: rejected because agency access is a scoped administrative
  capability across organization tenants.
- Defer all organization persistence: rejected because Phase 2 requires the tenant boundary before
  locations, memberships, products, and other scoped records can be implemented safely.

## Validation and review

Validate the organization schema, immutable slug, lifecycle transitions, optimistic concurrency,
atomic audit writes, internal-route guard, migration movement, and record-specific negative tests.
Review this decision only through a formally approved architecture revision.
