# Phase 5 Acceptance

Phase 5 establishes restart-safe workflow and job persistence through migration `20260803_0002`. It includes immutable workflow versions, organization-scoped runs and steps, durable jobs and attempts, schedules, leases, cancellation, bounded retries, terminal ambiguity handling, and idempotency conflict detection.

Acceptance checklist: durable intent before dispatch; no external action in a database transaction; duplicate-safe submission; concurrent claim protection; stale-lease recovery; attempts retained; bounded backoff and timeout; cancellation; audit-compatible caller-owned transactions; restrictive tenant foreign keys; authorization catalog coverage; Phase 4 policy/runtime/readiness references without duplication. No real provider action is implemented.

Known warning: the pre-existing Starlette/httpx test warning remains unchanged. Phase 5 status: complete.
