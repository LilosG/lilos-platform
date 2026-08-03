# Authorization evaluation framework

Phase 4 routes reuse this evaluator with fixed server permissions and organization scope. Fact
approval, entitlement transitions, configuration/policy activation, runtime-control mutation, and
offboarding require AAL2. Same-organization location validation preserves not-found equivalence.

## Boundary and prerequisites

Authentication and authorization are separate. A verified Supabase token maps to one active
platform user but grants no organization access. The read-only evaluator allows a request only
when the authenticated principal is active, the requested organization is `active`, an active
membership exists for that platform user and organization, the requested permission is granted by
an applicable fixed system-role assignment, no applicable explicit deny exists, and the verified
assurance level satisfies the fixed server-side route policy.

`prospect`, `onboarding`, `paused`, `suspended`, `offboarding`, and `archived` organizations do not
produce general runtime access. Onboarding exceptions require a later explicit route policy; none
exist in this packet. Invited, suspended, revoked, expired, or missing memberships do not produce
access. Evaluation changes none of these records.

## Deterministic evaluation

The evaluator validates the immutable request, verifies that its platform user matches the
authenticated principal, resolves the organization, membership, and optional organization-owned
location, verifies AAL, loads scoped assignments and the immutable permission catalog, loads scoped
denies, applies deny precedence, and returns an immutable internal decision. Missing or malformed
catalog/scope state and PostgreSQL read failures fail closed.

Organization-scoped role allows apply to organization actions and all current/future locations in
that organization. A matching location-scoped allow applies only to that location and never to an
organization action or sibling location. Multiple role allows are additive. There are no direct
allows, platform scope, all-locations scope, nested scope, or location-group authorization.

An applicable organization deny overrides every allow for the organization and its locations. A
matching location deny overrides every allow at that location. Owner, administrator, internal,
support, or any other role/membership classification cannot bypass a deny.

## MFA and domain lifecycle

The route policy chooses a minimum of `aal1` or `aal2`; clients cannot submit or lower it. AAL2
satisfies AAL1, while AAL1 does not satisfy AAL2. MFA assurance never creates a permission, and a
permission never bypasses the required assurance.

Authorization establishes permission, not domain validity. Every location lifecycle state remains
addressable for an otherwise permitted read. Organization and location services still reject
invalid mutations, transitions, and parent-state operations after authorization. The evaluator
does not duplicate or modify lifecycle state.

## HTTP and observability

Authenticated denials return generic no-store `403 AUTHORIZATION_DENIED`; internal membership,
role, permission, deny, organization-state, and assurance reasons are not exposed. Wrong-owner
location IDs retain the same ordinary not-found response as missing locations. Unauthenticated
requests retain the existing generic 401 contract.

Evaluation emits minimized structured security logs containing the correlation ID, outcome,
internal reason, authenticated platform-user ID, validated organization ID when available, fixed
permission key, scope category, and AAL values. Logs exclude tokens, authorization headers, email,
role/permission lists, deny details, and customer content. Evaluation creates no audit event,
decision table, persisted snapshot, or cache. Operational log retention remains infrastructure
policy.

## Enforced routes and continuity

The always-mounted `/api/v1` surface applies the evaluator to supported organization, location,
profile, location-group, business-identity, membership, invitation, assignment, deny, and catalog
operations. The route-access matrix fixes every permission, organization/location scope, AAL, and
not-found rule. Proof-only authorization-test routes have been removed.

Privilege-changing membership, role, deny, and invitation operations require AAL2. A locked
transactional guard prevents assignment removal, membership suspension/revocation, or user
deactivation from leaving an active organization without an active organization-scoped owner.
Owners retain no authorization or deny bypass. See ADR 0011 and
`docs/PHASE-03-ROUTE-AUTHORIZATION-MATRIX.md`.

RLS, product entitlements, location-group scope, and frontend administration remain deferred.
