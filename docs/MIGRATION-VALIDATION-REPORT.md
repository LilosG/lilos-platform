# Migration Validation Report

PostgreSQL 17 is upgraded from base to `20260803_0013`, checked for drift, downgraded in disposable storage, and re-upgraded. Tests inspect the audit trigger, immutable revisions, ownership constraints, RLS, catalogs, and table inventory. The production runbook requires preflight, backup, lock review, maintenance decision, head verification, and forward-remediation preference.
