# Business identity resolution

## Purpose and authority

Business identity is a deterministic read model for later products. It composes the current
organization, optional assigned industry, optional organization profile, and—when requested—one
organization-owned location and its optional profile. PostgreSQL records remain authoritative.
There is no `business_identity` table, persisted snapshot, cache, mutation operation, or audit event.

Every resolution requires `organization_id`. Location resolution additionally queries with both
`organization_id` and `location_id`; a location owned by another organization is indistinguishable
from a missing location. Industry lookup is the only global lookup and uses its controlled UUID
repository operation.

## Typed results

Organization identity exposes only bounded identity, lifecycle, timezone/currency, version,
optional industry identity/status, optional controlled profile context, and explicit presence
flags. It excludes contacts, addresses, policy JSON, configuration, and customer data.

Location identity adds bounded location identity/type/status/timezone/country/primary state,
optional location profile context, and a traceable resolved call to action. Organization and
location profiles remain separately represented.

All contracts are frozen and reject extra fields. Resolution is read-only and executes within the
caller's existing database transaction.

## Overrides, lists, and claims

`call_to_action_override` is the only resolved scalar because its override relationship is explicit:

1. A present location-profile override is returned with source `location_profile`.
2. Otherwise a present organization default is returned with source `organization_profile`.
3. Otherwise the value is null with source `none`.

Blank stored overrides are prevented by profile validation. No other scalar mapping is inferred.

Cross-level list behavior is undefined and therefore deliberately absent. Organization and
location services, approved claims, prohibited claims, tone fields, disclaimers, landmarks, and
references remain separately attributable. The resolver does not merge, replace, extend,
deduplicate, infer approval, erase prohibitions, or resolve cross-level claim contradictions.

## Missing data and lifecycle reads

An organization or location may lack its optional profile, and a legacy organization may lack an
industry. Presence flags and null values report these states directly. The resolver never assigns
`general_local_business`, derives profile values from base records, or fabricates defaults.

Reads are allowed for every established organization status (`prospect`, `onboarding`, `active`,
`paused`, `suspended`, `offboarding`, `archived`) and every location status (`setup_required`,
`active`, `paused`, `closed_temporarily`, `closed_permanently`, `archived`). This preserves
historical controlled context; future authentication and authorization will determine who may read
it.

Location groups are excluded. ADR 0007 limits them to administrative organization, selected-location
scope, and future reporting; they currently have no business-identity effect.

## Routes and authorization

- `GET /internal/organizations/{organization_id}/business-identity`
- `GET /internal/organizations/{organization_id}/locations/{location_id}/business-identity`

These read-only routes are unregistered by default. Explicit enablement is accepted only in local
or test; development, staging, and production reject it. They remain local diagnostics.

Production-capable equivalents live under `/api/v1/organizations/{organization_id}` and require
`business_identity.read` at organization or location scope. They preserve the same typed,
read-only, non-persisted behavior and wrong-owner location not-found equivalence. PostgreSQL RLS
remains later work.
