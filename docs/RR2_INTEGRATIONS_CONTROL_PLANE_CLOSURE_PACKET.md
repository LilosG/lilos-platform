# RR-2 — Non-Hermes Integrations Control-Plane Closure

## Goal
Make `/integrations` the canonical Google control plane for connection, account identity, GBP/GSC/GA4 mapping truth, freshness and read-side status without touching PR47 agent/workflow surfaces.

## Baseline
Branch from PR46 accepted commit `a91e64367810d7d45524b472a3007a6ba9fe1cb5`.

## Confirmed gaps
- Shared Google routes/status are gated by GBP-oriented authorization rather than neutral Google/integration authorization.
- Starting the shared Google connection requires effective GBP entitlement, blocking SEO- or Insights-only customers.
- OAuth callback returns to `/gbp` rather than the Integrations control plane.
- GSC and GA4 discovery/map/sync backend helpers exist but `/integrations` does not surface canonical mapping/freshness truth.
- Connected Google account identity and per-capability sync/health are incomplete.
- Email/SMS state is hard-coded `not_configured`; do not fabricate provider capability here.

## Ownership
- `apps/api/app/routes/integrations.py`
- `apps/api/app/integrations/directory_service.py`
- integration-local contracts/helpers if required
- `apps/web/src/lib/integrations.ts`
- `apps/web/src/lib/gbp-connection.ts`
- `apps/web/src/pages/integrations.astro`
- focused integration/browser tests
- release-ledger evidence for this packet only

## Exclusions
Do not modify:
- `apps/api/app/products/seo/**`
- `apps/api/app/products/analytics/**`
- execution/workflow/Hermes/AI files
- PR47 agent/tool files
- shared agent UI
- Leads provider dispatch
- GA4 mapping authority implementation inside AnalyticsService

## Required behavior
1. Shared Google connection/status/read paths use a neutral integration capability/authorization contract appropriate for any enabled Google-backed product, while preserving write-specific GBP permissions for GBP mutations.
2. SEO-only or Insights-only entitled organizations can establish/maintain the shared Google connection without requiring GBP entitlement.
3. OAuth callback returns to `/integrations` (or an integration-owned return target) and preserves safe state handling.
4. Integrations read model exposes connected account identity where authoritative evidence exists.
5. Integrations read model exposes canonical GBP, GSC and GA4 mapping/freshness/health by delegating to existing services/contracts; no duplicate provider state is introduced.
6. GSC/GA4 operator controls may call existing discovery/map/sync routes/helpers from the Integrations UX, but product services remain canonical.
7. Provider read failures, missing mapping, stale data and healthy/fresh states render distinctly.
8. Successful discovery/map/sync must refetch canonical backend truth.
9. Do not claim email/SMS operational readiness without a real provider implementation.
10. No provider write is introduced by this packet.

## Acceptance
- healthy existing Google connection is not re-prompted unnecessarily;
- SEO-only and Insights-only entitlement cases can use shared Google OAuth;
- callback lands on Integrations;
- exact mapped GBP/GSC/GA4 identities and freshness render from backend truth;
- unmapped and stale states are truthful;
- GSC/GA4 discovery controls use existing canonical product services rather than shadow state;
- tenant isolation and AAL requirements remain intact;
- no product provider mutation occurs.

## Validation
Focused integration/API/web/browser tests first. Then normal integrated repository validation exactly once. Stop on unrelated failure. Commit/push only if green; do not merge.

## Remaining known dependency
GA4 property mapping currently trusts caller-supplied provider identity. This packet must surface that state truthfully but must not modify AnalyticsService while PR47 owns overlapping Insights surfaces. Record it as a blocker for the post-PR47 re-audit.