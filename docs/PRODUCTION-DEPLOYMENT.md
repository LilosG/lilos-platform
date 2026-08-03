# Production Deployment Runbook

1. Record release, artifacts, approvers, change window, incident state, and rollback owner.
2. Run every Phase 18 release gate and production preflight; stop on any failure.
3. Verify secret access by identity without printing values, telemetry/alert paths, current encrypted backup, and restore evidence.
4. Verify private PostgreSQL 17, application/migration roles, extensions, constraints, triggers, catalog state, monitoring, PITR, and capacity.
5. Enter approved maintenance mode when migration lock analysis requires it. Take a backup, migrate once, verify head and controls, then seed immutable catalogs with mismatch detection.
6. Deploy immutable API, worker, scheduler, and frontend artifacts. Do not route traffic until readiness, heartbeats, queues, logs, metrics, traces, and alerts pass.
7. Run production-safe smoke tests and the approved pilot plan. Record every result and go/no-go decision.
8. Launch only with zero critical incidents, current rollback/restore evidence, active monitoring, and named approval.

This procedure has not been executed against production because accounts, values, authority, pilot, and approval are unavailable.
