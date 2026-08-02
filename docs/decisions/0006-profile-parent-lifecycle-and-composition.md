# ADR 0006: Profile parent lifecycle and composition boundaries

- Status: Accepted
- Date: 2026-08-02
- Decision owners: LILOs platform architecture

## Context

Organization and location profiles are controlled business context. The master specification
defines their ownership and content but does not assign profile administration permissions to
every organization and location lifecycle state. It also does not define how organization and
location list fields combine into a future effective business identity.

## Decision

Existing profiles remain readable in every parent lifecycle state, subject to organization scope
and future authorization controls.

Organization-profile creation and update are allowed when the organization is `prospect`,
`onboarding`, `active`, or `paused`. Organizations in `suspended`, `offboarding`, or `archived` are
read-only for profiles.

Location-profile creation and update are allowed when the location is `setup_required`, `active`,
`paused`, or `closed_temporarily`. Locations in `closed_permanently` or `archived` are read-only for
profiles.

For a location profile, the strictest parent rule wins: both the organization and location must
permit mutation. The service evaluates and locks both current parent records inside the same
caller-owned transaction used for the profile mutation and audit event. Cross-organization
location identifiers retain the same not-found behavior as missing identifiers. A profile
operation never changes a parent lifecycle state.

Both profile tables use optimistic integer versions. Profiles begin at version 1; updates require
the expected version and increment it exactly once through compare-and-swap persistence.

No effective-profile composition service is introduced. Organization and location profiles remain
separate. In particular, location list fields do not yet replace, extend, merge, or deduplicate
organization list fields. Effective list behavior is deferred to the later business-identity
packet. That future resolver must preserve enforceable prohibitions and must not silently treat
AI-generated content as approved business context.

## Consequences

- Paused organizations and paused or temporarily closed locations may correct controlled context
  or prepare it for future operation.
- Suspended, offboarding, permanently closed, and archived parents preserve existing profiles for
  audit and historical use but prohibit mutation as defined above.
- Denied writes return a stable parent-state conflict without exposing another organization's
  ownership.
- Profile services expose no delete, archive, reopen, restore, AI-write, or automatic-population
  behavior.
- Profile audit metadata contains identity, operation, version, and changed field names only; it
  excludes full content and claims.
