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

**Two-phase setup, driven by the existing authorization architecture.** The general
`/api/v1/organizations/{id}/...` routes (services, business facts, entitlements, policies,
additional memberships/invitations) all require the organization to already be `ACTIVE` — this is
the pre-existing, unchanged `ORGANIZATION_NOT_EFFECTIVE` gate in `AuthorizationService`. So
onboarding is naturally two phases:

1. **Pre-activation** (via the always-mounted, platform-administrator-gated
   `/api/v1/platform/organizations/{id}/...` routes, which bypass per-organization RBAC exactly as
   organization/location creation already did): organization profile, locations (with a primary),
   approved domains (with a primary), industry assignment, and bootstrapping the platform
   administrator's own account as the organization's first owner.
2. **Post-activation** (via the standard RBAC-protected organization routes, using the
   now-owner-privileged account from step 1): service assignment, business-fact proposal/approval,
   product entitlement creation, and approval/notification policy configuration. The onboarding
   workspace shows these sections as available once the organization is active, rather than hiding
   or faking their state beforehand.

**Activation gate.** `POST /api/v1/platform/organizations/{id}/activate` recomputes
`OnboardingState` server-side on every call and returns `409 ONBOARDING_INCOMPLETE` (with the exact
blocker list in `error.details`) unless `activation_eligible` is true. The frontend never decides
activation eligibility itself. Blocking requirements are: organization profile, at least one
location with one marked primary, an active primary domain, an assigned industry, and at least one
active member. A selected product's own missing business facts/entitlement/policy prerequisites are
tracked and shown, but external-integration-only findings
(`INTEGRATION_FOUNDATION_DEFERRED`) never block organization activation — only that product's own
readiness, consistent with the existing readiness engine's separation of entitlement from readiness.

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
