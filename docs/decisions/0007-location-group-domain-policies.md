# ADR 0007: Organization-scoped location-group domain policies

- Status: Accepted
- Date: 2026-08-02
- Decision owners: LILOs platform architecture

## Context

The roadmap names location groups and the master specification requires a selected-location scope,
but neither defines the initial persistence, membership, lifecycle, or parent-state contract.
Location groups must remain an organization-owned administrative grouping mechanism rather than a
second ownership, authorization, configuration, product, workflow, or business-identity layer.

## Decision

`location_groups` stores `id`, `organization_id`, bounded `name`, immutable scoped `key`, nullable
bounded `description`, `active|archived` status, UTC timestamps, nullable `archived_at`, and
optimistic `version`. Keys use the established 3–63 lowercase ASCII, letter-first, single-hyphen
contract, reject platform routing keys, are unique within an organization, and remain reserved
after archival.

`location_group_memberships` stores only `id`, `organization_id`, `location_group_id`,
`location_id`, and `created_at`. A location may belong to zero, one, or many groups; a group may
contain zero or more locations. Scoped uniqueness rejects duplicates. Memberships have no status,
order, priority, primary flag, metadata, or lifecycle beyond explicit add and removal.

Groups transition only from `active` to terminal `archived`. Active groups permit versioned name
and description replacement. Archival requires the expected version and retains memberships.
Archived groups remain readable, reject content mutation and new memberships, and allow explicit
membership cleanup where the organization permits it. Group keys and ownership never change, and
groups have no physical-delete operation.

Organization permissions are:

| Organization status | Read | Create | Update | Add member | Remove member | Archive |
| --- | --- | --- | --- | --- | --- | --- |
| `prospect` | yes | yes | yes | yes | yes | yes |
| `onboarding` | yes | yes | yes | yes | yes | yes |
| `active` | yes | yes | yes | yes | yes | yes |
| `paused` | yes | yes | yes | no | yes | yes |
| `suspended` | yes | no | no | no | no | no |
| `offboarding` | yes | no | no | no | yes | yes |
| `archived` | yes | no | no | no | no | no |

New membership permits locations in `setup_required`, `active`, `paused`, or
`closed_temporarily`; it rejects `closed_permanently` and `archived`. Existing membership persists
through every later location state. Location lifecycle changes never modify memberships.

Every record carries organization ownership, and composite foreign keys require memberships to
match both their group and location organization. Nested groups are prohibited.

The current purpose is administrative organization, selected-location scope, and future reporting
scope only. Groups do not influence authorization, permissions, entitlements, configuration,
profiles, integrations, workflows, business identity, or billing. Those effects require a future
approved architecture decision.

## Consequences

- Group and membership reads and mutations are organization-scoped and cannot reveal another
  organization's ownership.
- Group changes use compare-and-swap concurrency; parent, group, and location rows are locked for
  relevant mutations.
- Group and membership mutations append bounded audit evidence in the caller-owned transaction.
- Membership removal is the only authorized physical membership-row deletion; group deletion,
  bulk reassignment, automatic membership, and recursive behavior are absent.
- Authentication, authorization, request organization context, RLS, reporting execution, and
  frontend administration remain later work.
