# Phase 12 Acceptance

Migration `20260803_0009` establishes evidence-backed opportunities, structured briefs, immutable grounded revisions, distinct approvals, controlled repository targets, durable publication intent, build/deployment/verification states, reconciliation, and rollback lineage. Repository paths are allowlisted and traversal-safe; no token or repository content is stored in audit/log records. The shared AI gateway is reused.

The prior "Phase 12 status: complete" claim covered the domain model and a
publish-reservation stub only. Corrected this pass: every opportunity
identification/decision, item creation, brief, revision draft, approval
decision, and publication reservation now writes a real audit event via the
shared `AuditEventService`/`AuditEventRepository`; revisions entering
editorial or client review raise real in-app notifications via the shared
`NotificationService` (org-scoped `NotificationTemplate` rows are lazily
created, matching the Reviews/Leads pattern); a new AI-assisted drafting
path drives content generation through the existing `AIGateway` with the
safe, credential-free `DeterministicAIProvider`, persisting a governed
`AITaskDefinition`/`AIExecution` record and always requiring editorial and
client review before publication; a typed `errors.py` module replaced bare
`LookupError`/`ValueError` raises that previously fell through to
unhandled 500s; publication reservation now verifies the publishing
target's underlying `IntegrationConnection` is actually connected before
reserving, not just that the target row exists; tenant-scoped
opportunity/item/brief/revision/publication/target list, detail, summary,
and audit-history read routes were added, reusing existing shared services
for authentication, authorization, entitlements, AI routing, notifications,
and audit — no duplicate product-specific infrastructure. A real protected
`/content` frontend route renders truthful readiness, an opportunity queue
with accept/reject, a content pipeline with filters, and a detail view with
brief creation, manual and AI-assisted drafting, editorial/client approval,
and publication reservation — no fixture data, no dead buttons. 8 new
backend integration tests plus a new Playwright case were added; full
repository validation was run.

GitHub/Astro behavior is contract-tested offline. Live branch creation, pull
request creation, build verification, deployment verification, and rollback
against a real repository remain genuinely blocked on a real per-organization
GitHub App or PAT connection, which was not configured or requested this
pass — the same category of blocker as GBP's live Google write access.
Publication reservation is real and durable, but does not perform a live
write to any repository. Existing Starlette/httpx warning remains unchanged.
Phase 12 status: complete for all work not blocked on a live repository
connection.
