# Backup and Restore

CI creates a PostgreSQL custom-format backup of synthetic head data, restores it into a separate database, then verifies migration head, critical structures, and the audit append-only trigger. Production policy requires encrypted managed backups, PITR where supported, access controls, freshness alerts, retention, and a separate restore environment. Production RPO/RTO evidence cannot be accepted until the production destination is provisioned and restored.

On 2026-08-03 the same procedure restored the disposable PostgreSQL 17 Phase 18 database into a second local database and `scripts/verify_restored_database.py` verified migration head `20260803_0013`, critical tables, and append-only audit protection. The backup and restored database were then removed. This is synthetic restore evidence, not production-backup evidence.
