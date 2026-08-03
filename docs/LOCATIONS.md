# Locations

Locations are organization-owned operating units. Every repository read and mutation requires `organization_id`; a cross-organization identifier is indistinguishable from a missing identifier. Authorization and PostgreSQL RLS are not implemented yet.

## Schema and classifications

`locations` contains exactly: `id`, `organization_id`, `name`, `slug`, `location_type`, `status`, `timezone`, `address_line_1`, `address_line_2`, `city`, `region`, `postal_code`, `country_code`, `latitude`, `longitude`, `service_area_description`, `phone`, `email`, `website_url`, `external_reference`, `is_primary`, `archived_at`, `created_at`, `updated_at`, and `version`.

Types are `physical`, `service_area`, `hybrid`, and `virtual`. Department hierarchy is deferred. Statuses are `setup_required`, `active`, `paused`, `closed_temporarily`, `closed_permanently`, and `archived`.

- Physical requires `address_line_1`, `city`, `region`, `postal_code`, and `country_code`.
- Service area requires `service_area_description` and `country_code`; its four core street-address fields must be supplied together or omitted together.
- Hybrid requires the complete physical address, country, and service-area description.
- Virtual requires `website_url` and `country_code` and forbids every address field, coordinates, and service-area description.

Timezone is an IANA identifier. Country is an uppercase two-letter code. Contact and external-reference fields are bounded. Audit metadata deliberately excludes address and contact data.

## Slug, primary, and lifecycle rules

Slugs are trimmed and lowercased, 3–63 lowercase ASCII characters, begin with a letter, contain only letters/numbers/single hyphens, and cannot end in a hyphen. Punctuation is not rewritten. `admin`, `api`, `internal`, `platform`, `public`, `system`, `support`, and `www` are reserved. A database trigger prevents slug mutation; `(organization_id, slug)` stays unique after archival.

A partial unique index permits zero or one primary location per organization. Virtual locations may be primary. Archival does not choose a replacement.

The lifecycle and organization-parent restrictions are defined in [ADR 0005](decisions/0005-location-foundation-policies.md). Each mutation requires `expected_version`; the compare-and-swap update increments version once. No repository delete or general update operation exists. Stronger production-role enforcement remains deferred.

## Transactions, audit, and routes

Creation and lifecycle mutations append organization- and location-scoped audit events through the same caller-owned `AsyncSession`. Neither service commits. Owning transaction failure rolls back both records. Audit location references use `ON DELETE RESTRICT`, while existing append-only controls remain unchanged.

Temporary routes live below `/internal/organizations/{organization_id}/locations`. They are unregistered by default and can be explicitly enabled only in local/test. They are unauthenticated bootstrap surfaces and are not production-safe.

A location may have zero or one organization-scoped controlled profile. Reads remain allowed in
every parent state. Profile create/update require both an organization that permits profile
mutation and a location in setup-required, active, paused, or temporarily closed state. Permanently
closed and archived locations are read-only. Effective organization/location profile composition
is deferred. See `docs/PROFILES.md` and ADR 0006.

A location may belong to zero, one, or many organization-owned location groups. Existing
membership persists through pause, closure, or archival and is removed only through an explicit
audited operation. Location lifecycle changes never alter membership. Groups do not change
location ownership, configuration, profiles, entitlements, workflows, or authorization. See
`docs/LOCATION-GROUPS.md` and ADR 0007.

Current location business identity is resolved with both organization and location scope. Closed
and archived locations remain readable, optional profiles remain explicit, cross-level lists stay
separate, and location groups are excluded. See `docs/BUSINESS-IDENTITY.md` and ADR 0008.

Role assignments and explicit denies may target one organization-owned location. Composite foreign
keys prevent cross-organization scope. Organization scope applies to all current/future locations;
location scope applies only to that location. Permissions never bypass lifecycle restrictions.
