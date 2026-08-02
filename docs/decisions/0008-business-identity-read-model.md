# ADR 0008: Business identity is a computed read model

- Status: Accepted
- Date: 2026-08-02
- Decision owners: LILOs platform architecture
- Related roadmap phase: Phase 2

## Context

Phase 2 requires business identity to resolve by organization and location. The authoritative
records already exist as organizations, locations, industries, and optional organization/location
profiles. The specification authorizes location overrides where defined but does not define a
general cross-level list merge. ADR 0007 also explicitly excludes location-group effects from
business identity at this stage.

## Decision

Business identity is computed transactionally from current authoritative records through a
read-only application service. It has no table, snapshot, cache, mutation method, or audit event.
Every operation requires organization scope, and location resolution requires both organization
and location identifiers in the location and profile queries.

The organization result contains a bounded organization identity, optional assigned industry, and
optional organization profile. The location result adds bounded location identity and the optional
location profile. Missing profiles and legacy missing industries are represented explicitly and do
not create fabricated defaults.

Organization and location list fields—including services, claims, tone, disclaimers, landmarks,
and references—remain separately attributable. They are not replaced, extended, merged, or
deduplicated. Claims are not inferred or reconciled across levels. The explicitly named
`call_to_action_override` is the only resolved scalar: a present location value wins; otherwise the
organization default is retained. The result records the selected source.

Identity reads are allowed in every established organization and location lifecycle state,
consistent with ADR 0006's preservation of controlled profile reads. Location-group memberships
are excluded because ADR 0007 limits groups to administrative selection and future reporting.

## Consequences

- Current identity cannot drift from a separately persisted duplicate.
- Read resolution causes no mutation or audit event.
- Closed, archived, suspended, and offboarding records remain available for controlled historical
  reads, subject to future authorization.
- Consumers must handle explicit profile and industry absence.
- Final list composition, claim-conflict policy, configuration inheritance, and group-derived
  context require later explicit authority.

## Validation and review

Validate exact immutable contracts, missing data, all lifecycle states, scalar source selection,
separate list/claim attribution, cross-organization denial, guarded routes, absence of a database
table, and complete Phase 2 regressions. Review only when a later business-facts, configuration,
authorization, or product packet defines additional composition semantics.
