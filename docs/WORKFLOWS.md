# Workflow and Job Foundation

Phase 5 provides one shared durable execution model. Workflow definitions are versioned; runs and jobs are organization-owned; submissions are deduplicated by an organization-scoped idempotency key and canonical request hash. Jobs are claimed with PostgreSQL row locking and bounded leases. Expired claims may be recovered, attempts are retained, retry uses bounded exponential backoff, ambiguous outcomes dead-letter rather than replay blindly, and cancellation prevents future claims.

External adapters must run only after the intent transaction commits. They must use the durable job idempotency key and persist only bounded result references. Approval gates refer to Phase 4 policies. Entitlement, readiness, runtime controls, authentication, and authorization remain distinct preconditions.

The worker and scheduler entrypoints consume this model; no second queue or scheduler is authorized. Phase 5 includes deterministic test handlers only and performs no provider action.
