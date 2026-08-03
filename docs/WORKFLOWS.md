# Workflow and Job Foundation

Phase 5 provides one shared durable execution model. Workflow definitions are versioned; runs and jobs are organization-owned; submissions are deduplicated by an organization-scoped idempotency key and canonical request hash. Jobs are claimed with PostgreSQL row locking and bounded leases. Expired claims may be recovered, attempts are retained, retry uses bounded exponential backoff, ambiguous outcomes dead-letter rather than replay blindly, and cancellation prevents future claims.

External adapters must run only after the intent transaction commits. They must use the durable job idempotency key and persist only bounded result references. Approval gates refer to Phase 4 policies. Entitlement, readiness, runtime controls, authentication, and authorization remain distinct preconditions.

The production worker continuously claims through `ExecutionService`, persists attempts, renews its
lease while a handler is active, and completes the workflow envelope and job outcome atomically.
Unknown job types, missing runs, non-approved workflow versions, and non-empty step specifications
without a registered handler fail closed; the runtime never guesses an operation. Idle polling uses
bounded interruptible backoff and does not busy-loop. The scheduler locks due records with
`SKIP LOCKED`, uses schedule identity plus the scheduled instant as the idempotency key, advances
timezone-aware cron state in the same transaction as workflow/job creation, and never executes the
workflow itself. Both processes maintain persisted operational heartbeats and stop cooperatively on
SIGTERM/SIGINT. No second queue or scheduler is authorized, and no provider action is introduced by
the process entrypoints.
