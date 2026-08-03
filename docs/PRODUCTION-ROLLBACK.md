# Production Rollback Runbook

Rollback criteria include readiness failure, elevated release error rate, tenant-isolation or authorization concern, migration inconsistency, duplicate external actions, or failed smoke/pilot gates. Pause external work and scheduling first, preserve durable intents and reconciliation state, and declare an incident.

Frontend, API, worker, and scheduler roll back to previous immutable compatible artifacts. Configuration and flags use governed revisions. Database downgrade is used only when explicitly proven safe; otherwise hold traffic and forward-remediate or restore the pre-migration backup. Re-enable work only after schema compatibility, readiness, heartbeats, tenant isolation, audit protection, queues, provider reconciliation, and smoke checks pass. Record decision, release identities, evidence, and approver. No production rollback was exercised because production access is unavailable.
