# Phase 9 Acceptance — First End-to-End Vertical Slice: Google Business Profile

This document supersedes the prior version, which stated "Phase 9 status: complete" based on the
existence of migration `20260803_0006`'s data models and an offline connector-contract suite. That
was inaccurate: no API routes existed for discovery or history, no audit events were ever written
by any GBP action, and no frontend existed at all. This version reconciles actual code against the
roadmap's real Phase 9 exit criteria and records what this pass completed.

## Reconciliation against the roadmap

Roadmap Phase 9's exit criteria are the nine-step vertical slice: connect Google, select account,
map location, sync profile, review proposed change, approve, publish, verify provider state,
inspect audit/workflow history. The exhaustive GBP feature list (categories, hours, attributes,
services, products, media, posts, Q&A, completeness scoring, conflict detection, scheduled
actions, reporting, operational alerts) belongs to **Roadmap Phase 14 — Remaining Google Business
Profile Capabilities**, a separate later phase, not Phase 9. This document does not invent a
replacement phase structure; it reconciles actual code against the phases as defined in
`LILOS-BUILD-ROADMAP.md`.

Before this pass, the backend held complete data models for both Phase 9 and Phase 14 (migrations
`20260803_0006` and `20260803_0011`), but:

- The API surface exposed only 5 routes (confirm mapping, read profile, propose/decide/publish a
  change) — no discovery, no read access to change/publication history, and **no audit events were
  ever written** by any GBP mutation despite the roadmap listing "Audit" as a Phase 9 deliverable.
- The Integration Framework (Phase 7/8) that Phase 9 depends on for "Connect Google" has complete
  persistence (`Provider`, `IntegrationConnection`, `OAuthAuthorizationIntent`,
  `ProviderResourceMapping`) and an `OAuthIntentService`, but **zero HTTP routes**, no `SecretStore`
  implementation (only a `Protocol`), and no Google OAuth client configuration. This is not an
  oversight: the platform's own readiness engine
  (`apps/api/app/administration/service.py::readiness`) already emits a deliberate, explicit
  blocking finding — `INTEGRATION_FOUNDATION_DEFERRED`, remediation "Connect the required
  integration when the integration foundation is available" — whenever a product declares a
  `required_integrations` entry. GBP's readiness has always correctly reported `blocked` for this
  reason; this is intentional, existing platform design, not new evidence.
- No workflow job handler exists for actually dispatching a GBP write to Google, verifying it, or
  reconciling ambiguous results — `execution/runtime.py`'s single generic job type
  (`workflow.execute`) has no registered step handler at all yet, for any product.
- The frontend had no Business Profile route, page, or component whatsoever.

## What this pass completed

**Backend** (`apps/api/app/products/gbp/service.py`, `apps/api/app/routes/gbp.py`,
`apps/api/app/main.py`):

- Every GBP mutation (`confirm_mapping`, `propose`, `decide`, `reserve_publication`) now writes a
  real audit event through the existing shared `AuditEventService` — no duplicate audit
  infrastructure was created.
- New read routes, all tenant-scoped and permission-checked using the existing fixed-permission
  catalog (`gbp.read`, `audit.read`, all already seeded — no catalog changes required):
  - `GET /api/v1/organizations/{org}/gbp/accounts` — discovered GBP accounts (org-scoped)
  - `GET /api/v1/organizations/{org}/gbp/locations` — discovered GBP locations (org-scoped,
    optional `mapping_status` filter)
  - `GET .../gbp/changes/{revision_id}` — change revision detail
  - `GET .../gbp/changes/{revision_id}/audit` — change audit history
  - `GET .../gbp/publications` — publication history for a mapped location
  - `GET .../gbp/publications/{id}/audit` — publication audit history
  - `GET .../gbp/locations/{gbp_location_id}/audit` — mapping audit history
- All new routes reuse the existing shared authentication, authorization, tenant-scoping, and
  audit services. No product-specific duplicate infrastructure was created. No migration was
  required — every new route reads models that already existed.

**Frontend** (`apps/web/src/pages/gbp.astro`, `apps/web/src/lib/gbp.ts`,
`apps/web/src/lib/platform.ts`):

- A real, protected `/gbp` route reachable from the always-rendered sidebar navigation (previously
  the "Business Profile" nav item only anchored to the dashboard).
- Client-side boot sequence identical in pattern to the existing dashboard (`index.astro`):
  redirects unauthenticated visitors to `/login`, shows the truthful not-configured state when
  deployment configuration is absent, then fetches the real principal, real organization, real
  product readiness, real discovered accounts, and real discovered locations.
- Readiness is rendered from the platform's own existing readiness endpoint and shows the real
  `blocked` state with the real `INTEGRATION_FOUNDATION_DEFERRED` remediation text when it applies
  — not a fabricated status.
- Accounts and locations render real API data; with none discovered (the true current production
  state), the page shows an explicit, honest empty state ("No Google accounts discovered yet.
  Connecting Google is not yet available in this release.") rather than fixture data or a dead
  button.
- Categories/hours/attributes/services/products/media/posts (Phase 14 scope) are shown in one
  explicit "not available in this release" panel — never simulated.
- Every list independently handles its own `forbidden`/`disconnected`/`error` outcome and reports
  it inline, rather than silently showing an empty list on failure.

**Tests**: `tests/python/gbp/test_gbp_api.py` (new, 11 cases) covers the full mapping → propose →
approve → publish flow end to end against a real PostgreSQL-backed test app, asserts every
mutation produces a readable, correctly-typed audit event, and asserts cross-tenant reads of
locations/changes/publications are rejected. `tests/browser/release.spec.ts` gained a Playwright
case asserting the unconfigured `/gbp` build shows the truthful not-configured state, not
fabricated GBP data. Full repository validation (format, lint, strict mypy, Vitest, full pytest,
Astro build, Playwright + accessibility) was run; see the accompanying commit for exact results.

## Exact remaining Phase 9 blocker

**"Connect Google" cannot be made live, and no real Google data can ever appear, without:**

1. **Google Cloud OAuth client credentials** (client ID and secret) — an external provider
   credential that does not exist and this session cannot create. Required for the OAuth
   authorization redirect and token exchange.
2. **A secret-encryption-at-rest key** for a real `SecretStore` implementation — a new production
   secret that does not exist. `IntegrationConnection.credential_reference` is designed to hold an
   opaque reference into such a store; implementing that store without a real encryption key would
   mean either inventing insecure storage or leaving it non-functional, and this session will not
   do the former.
3. **A registered workflow job handler** for dispatching/verifying/reconciling a GBP provider
   write — genuinely buildable without external credentials, but intentionally deferred this pass
   as a distinct, security-sensitive unit of work that deserves its own focused implementation and
   review rather than being rushed alongside the above.

Attempting to force a live "Connect Google" experience without (1) and (2) would mean either a
fake success (prohibited) or shipping incomplete secret handling (a security compromise this task
explicitly forbids). The truthful, currently-correct behavior — GBP reports `blocked` with a real
remediation, and the frontend shows a real, empty, honestly-labeled discovery state — is preserved
and was independently verified, not assumed.

## Deferred (Roadmap Phase 14, not Phase 9)

Categories, services, products, hours, special hours, attributes, description, photos, posts,
Q&A, completeness scoring, conflict detection, proposed-change sets, scheduled actions, GBP
reporting, and GBP operational alerts remain unimplemented at the API/frontend layer, consistent
with their roadmap phase. Their data models already exist (migration `20260803_0011`); no new
schema work is required when Phase 14 is taken up.
