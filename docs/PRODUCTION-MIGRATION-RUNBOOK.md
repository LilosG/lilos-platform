# Production Migration Runbook

Use a dedicated least-privilege migration identity. Confirm PostgreSQL 17, current head, free capacity, lock/statement timeouts, active workload, backup freshness, tested restoration, and rollback/forward-remediation decision before migration. Drain or enter maintenance when lock analysis requires it. Run Alembic upgrade exactly once from the immutable release, verify final head `20260803_0013`, tenant ownership constraints, audit/immutable triggers, indexes, RLS where present, and catalog mismatch detection.

Never run a destructive production downgrade as a diagnostic. Prefer forward remediation when durable records or audit references would be endangered. On failure, preserve redacted logs, hold traffic, assess transaction state, restore only under the approved recovery decision, and open an incident.
