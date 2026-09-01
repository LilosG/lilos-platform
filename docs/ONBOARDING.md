# Client-onboarding workspace

A platform administrator can onboard and activate a real client organization entirely from the
production web application at `/onboarding`, with no shell access, manual database change,
manually-entered UUID, or provisioning script required for the ordinary path.

**Architecture.** `apps/api/app/onboarding/` is a read-only orchestration layer
(`OnboardingOrchestrationService.get_state`) that composes the existing organization, location,
domain, profile, administration (services/business-facts/entitlements/policies/onboarding
checklist), and access-control services into one `OnboardingState`: per-step completion, per-product
selection/readiness (reusing `AdministrationService.readiness` verbatim), blockers, warnings, and a
progress percentage. It introduces no new authoritative business rule — every fact is resolved live
from the owning domain service at request time.

**Website/domain registry.** `apps/api/app/domains/` adds `OrganizationDomain` (migration
`20260805_0002`): one or more approved domains per organization, exactly one active primary,
audited create/set-primary/archive. This is new — previously the platform had only a single
`website_url` scalar field on `Organization`/`Location`, with no primary/additional-domain concept.

**Source-first setup.** Onboarding separates read-only source configuration from operational
provider writes. A platform administrator can create the organization, automatically establish its
profile and owner membership, add a primary location and domain, connect Google, discover and map a
Business Profile location, and start the first website crawl before activation. Discovery and
mapping reconcile source-backed business-fact candidates immediately, so the operator reviews and
confirms details instead of re-entering information already available from the client's website or
Google profile.

The onboarding authorization allowlist permits only the read/setup side of Integrations and GBP
(`integrations.read`, `integrations.connect`, `gbp.read`, and `gbp.connect`). Provider mutations,
proposals, publishing, workflow execution, and other operational product actions remain denied
until the organization is active and the normal organization-scoped policy authorizes them. This
keeps setup resumable without weakening the provider-write boundary.

The operator flow is presented as five high-level stages: Client details, Source data, Products,
Review, and Activate. The underlying single onboarding engine and its managed, co-managed, and
self-service responsibility modes remain unchanged.

**Activation gate.** `POST /api/v1/platform/organizations/{id}/activate` recomputes
`OnboardingState` server-side on every call and returns `409 ONBOARDING_INCOMPLETE` (with the exact
blocker list in `error.details`) unless `activation_eligible` is true. The frontend never decides
activation eligibility itself. Blocking requirements are: organization profile, at least one
location with one marked primary, an active primary domain, an assigned industry, and at least one
active member. Product selection, business facts, location profile, policies, configuration,
integration health, and runtime controls remain visible in each selected product's readiness
result, but they are setup warnings rather than organization-activation blockers. Activation means
the client workspace exists and can be operated; it does not claim that every selected product is
ready to run or publish.

**Invitations.** Adding an existing user or inviting a new one resolves the target by email
(`AccessControlService.find_user_by_email`) rather than a client-supplied UUID. A `UserProfile` is
only ever created on that person's first real sign-in (there is no Supabase admin credential in
this codebase to pre-provision an identity for someone who has never authenticated) — inviting
someone who hasn't signed in yet returns a truthful `USER_ACCOUNT_NOT_FOUND` explanation rather than
a fabricated "invitation sent" success state.

# Onboarding checklist

Items are organization-owned requirements with stable key, optional location/product scope,
blocker/warning severity, automated/manual classification, remediation, evidence, permission,
version, and audit history. Manual completion requires bounded evidence and actor. Automated items
cannot be completed by a checkbox; deterministic evidence remains owned by its source domain.

Resolution returns outstanding blockers and warnings. Completion requires no remaining blocker and
does not fabricate product readiness. No frontend is included.
