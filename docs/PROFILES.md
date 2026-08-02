# Controlled organization and location profiles

## Purpose and separation

Organization profiles hold shared business context. Location profiles hold context that is
specific to one organization-owned operating location. Both are optional, controlled business
records. They are not provider snapshots, generic configuration stores, AI memory, or unrestricted
metadata.

The Phase 2 business-identity resolver exposes both profiles separately. It does not compose
cross-level lists or claims because no replace, extend, merge, or deduplication rule is authorized.
The explicitly named `call_to_action_override` is the sole resolved scalar and reports whether its
value came from the location profile, organization profile, or neither. See
`docs/BUSINESS-IDENTITY.md` and ADR 0008.

## Organization profile

An organization has zero or one profile. `organization_profiles` stores UUID `id`, required unique
`organization_id`, the eleven specification content fields, UTC `created_at` and `updated_at`, and
positive optimistic `version`.

Scalar fields are nullable bounded text: `brand_name` (200), `brand_summary` (1,000),
`business_description` (8,000), `value_proposition` (4,000), `target_customer` (4,000), and
`default_call_to_action` (1,000 characters).

`primary_services`, `approved_claims`, `prohibited_claims`, `tone_guidelines`, and
`legal_disclaimers` are nullable PostgreSQL arrays of bounded strings.

## Location profile

A location has zero or one profile. `location_profiles` stores UUID `id`, required
`organization_id` and unique `location_id`, the nine specification content fields, UTC timestamps,
and positive optimistic `version`.

Scalar fields are nullable bounded text: `local_description` (8,000), `service_area` (4,000), and
`call_to_action_override` (1,000 characters).

`primary_services`, `local_landmarks`, `local_references`, `approved_claims`,
`prohibited_claims`, and `tone_overrides` are nullable PostgreSQL arrays of bounded strings.
A composite foreign key proves that the location belongs to the supplied organization. All
repository access includes both identifiers; a cross-organization location ID is indistinguishable
from a missing ID.

## Controlled collections and claims

Every collection permits at most 50 entries and at most 16,384 serialized bytes. General items are
limited to 500 characters; legal disclaimers are limited to 2,000. Validation collapses internal
whitespace, rejects blank entries and case-insensitive duplicates, and rebuilds the list before
persistence so later caller mutation cannot alter the profile.

Approved and prohibited claims remain separate. A normalized claim cannot appear in both lists in
one submitted profile. The platform never infers approval from industry, contact, website,
provider, or AI content. Cross-level effective claim and list resolution remains deferred; future
resolution must preserve enforceable prohibitions.

## Lifecycle permissions

Reads are allowed for an existing profile in every parent state, subject to organization ownership
and future authorization.

Organization-profile create/update is permitted for `prospect`, `onboarding`, `active`, and
`paused`; `suspended`, `offboarding`, and `archived` are read-only.

Location-profile create/update additionally requires a location in `setup_required`, `active`,
`paused`, or `closed_temporarily`; `closed_permanently` and `archived` are read-only. The strictest
parent rule wins. Services lock and evaluate current parent rows in the same transaction before the
profile write. See [ADR 0006](decisions/0006-profile-parent-lifecycle-and-composition.md).

## Updates, audit, and non-deletion

Profiles begin at version 1. Typed `PUT` replacement requires `expected_version`; one atomic
compare-and-swap increments the version once. A stale request returns a profile-specific conflict.
There is no physical delete, archive, restoration, arbitrary-column update, bulk import, AI write,
or automatic population method.

Create and update audit events share the caller-owned transaction with the profile mutation. Audit
metadata includes profile ID, operation, resulting version, and sorted changed-field names. It
never includes descriptions, services, claims, guidance, disclaimers, landmarks, references, or
CTA content. Profile IDs remain audit resource references without foreign keys, preserving
immutable audit evidence across a destructive disposable migration downgrade.

## Temporary administration boundary

The profile routes are temporary unauthenticated bootstrap surfaces. They remain unregistered by
default, may be enabled only in local/test, and are rejected in development, staging, and
production. Authentication, authorization, request organization context, and PostgreSQL RLS remain
future work. These routes are not production-safe.
