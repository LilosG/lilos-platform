# Phase 11 Acceptance

Migration `20260803_0008` establishes verified sources, normalized leads, preserved submissions, explicit consent evidence, immediate suppression, status history, durable communications, and CRM mappings/conflicts. Lead tables use forced PostgreSQL tenant RLS plus server authorization. Unknown consent is fail-closed. Opt-out cancels queued communication. Personal fields are absent from list responses and operational metadata.

The prior "Phase 11 status: complete" claim covered only intake, consent, and
communication planning. Corrected this pass: migration `20260804_0001` adds
`lead_notes` and `lead_tasks` tables (forced tenant RLS, same pattern as the
Phase 10 tables) plus `converted_value_cents` and `loss_reason` columns on
`leads`; every intake, consent record, communication plan, assignment,
status transition, note, and task now writes a real immutable audit event
via the shared `AuditEventService`/`AuditEventRepository`; lead assignment
and conversion raise real in-app notifications via the shared
`NotificationService` (org-scoped `NotificationTemplate` rows are lazily
created, matching the Reviews pattern); a status-transition guard
(`can_transition`) rejects moves out of terminal states except into
`archived`, returning a typed `409`; a typed `errors.py` module replaced
bare `LookupError` raises that previously fell through to unhandled `500`s;
tenant-scoped list/detail/summary/source-performance/notes/tasks/
communications/consents/audit-history read routes and assignment,
status-transition, conversion, loss, note, and task-completion write routes
were added, all reusing existing shared services for authentication,
authorization, entitlements, workflow, and audit — no duplicate
product-specific infrastructure. List responses continue to omit contact
identity (name, email, phone, message); the single-lead detail route
returns full contact identity under the same `leads.read` permission and
tenant scope. A real protected `/leads` frontend route renders truthful
readiness, an inbox with status/urgency/search filters, a detail view with
assignment, lifecycle, conversion, and loss controls, notes, follow-up
tasks, communication history, and audit history — no fabricated leads,
metrics, or CRM state, and no dead buttons. 8 new backend integration tests
plus a new Playwright case were added; full repository validation was run.

Provider-neutral notification and CRM boundaries use deterministic tests and no real personal data or credentials. Existing Starlette/httpx warning remains unchanged. Live email/SMS dispatch and CRM sync remain genuinely blocked on external provider credentials, which were not configured or requested this pass. Phase 11 status: complete for all work not blocked on live external provider access.
