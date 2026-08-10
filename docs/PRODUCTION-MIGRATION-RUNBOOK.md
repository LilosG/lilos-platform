# Production Migration Runbook

Use a dedicated least-privilege migration identity. Confirm PostgreSQL 17, free capacity, lock/statement timeouts, active workload, backup freshness, tested restoration, and the rollback/forward-remediation decision before migration. From the immutable release artifact, run `alembic heads` and record the single expected revision; stop if the graph has multiple heads. Run `alembic upgrade head` exactly once, then use `alembic current` to verify the database is at that recorded release head. Verify tenant ownership constraints, audit/immutable triggers, indexes, RLS where present, and catalog mismatch detection.

Never run a destructive production downgrade as a diagnostic. Prefer forward remediation when durable records or audit references would be endangered. On failure, preserve redacted logs, hold traffic, assess transaction state, restore only under the approved recovery decision, and open an incident.
