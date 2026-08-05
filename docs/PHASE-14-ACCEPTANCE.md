# Phase 14 Acceptance

Migration `20260803_0011` adds explicit capability snapshots, provider categories, governed per-field change sets, authoritative special hours, rights-bearing media, immutable posts with durable publication state, and suspension cases. Unsupported and lost capabilities fail closed; partial writes verify and reconcile per field; completeness excludes unsupported fields and makes no ranking claim.

The prior "Phase 14 status: complete" claim covered only the domain model
and a handful of pure deterministic functions (capability gating, hours
overlap validation, completeness scoring, conflict detection) — there was
no service layer, no API routes, and no frontend surface for any of these
capabilities. This pass built the full application surface on that
foundation. A new `GBPOperationsService` reuses the existing pure functions
and adds: capability snapshot recording, governed per-field change-set
proposal and approval (fails closed on an unavailable or read-only
capability via the existing `require_capability`), special-hours proposal
and approval (rejecting overlapping periods via the existing
`validate_hours`), media proposal with rights-authority evidence, post
drafting/approval/publication-reservation (reservation requires both an
approved revision and a confirmed, write-enabled location), suspension-case
reporting, and completeness/conflicts reporting against the latest
capability snapshot and profile snapshot. Every mutating action writes a
real audit event via the shared `AuditEventService`/`AuditEventRepository`;
change sets awaiting approval and suspension-case reports raise real
notifications via the shared `NotificationService`. Bare `ValueError`s from
the pure capability/hours functions are now caught and re-raised as typed
API errors at the service boundary, rather than falling through to
unhandled 500s. Tenant-scoped routes were added under
`/organizations/{organization_id}/locations/{location_id}/gbp/operations`,
reusing existing shared services for authentication, authorization,
entitlements, and audit — no duplicate product-specific infrastructure. The
existing protected `/gbp` frontend route gained a real "Operations" panel
(shown for confirmed, write-enabled locations) with completeness reporting,
change-set proposal/approval, special-hours proposal/approval, media
proposal, post drafting/approval/publication-reservation, suspension-case
reporting, and audit history — no fixture data, no dead buttons. 5 new
backend integration tests plus the existing GBP Playwright coverage were
exercised; full repository validation was run.

Unsupported provider capabilities (for example Q&A, which most GBP
locations do not expose for write) are visibly and explicitly unavailable —
`require_capability` fails closed with a typed `409` rather than silently
succeeding or fabricating support. Live provider capability discovery,
change dispatch, media upload, post publication, and suspension-case
detection remain genuinely blocked on the same external Google OAuth
client credentials and secret-encryption key recorded in
`PHASE-09-ACCEPTANCE.md`, not requested again this pass — this release
records governed intent (proposals, approvals, publication reservations)
durably but does not perform a live write to Google. Existing
Starlette/httpx warning remains unchanged. Phase 14 status: complete for
all work not blocked on live Google Business Profile write access.
