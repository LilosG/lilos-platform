# Content Publication and Rollback Runbook

Before dispatch recheck current approved hash, authorization/AAL2, entitlement, readiness, approval policy, runtime controls, connection/target health, base commit, path, and idempotency. If the base moved, stop and rebase through a new reviewed revision. Build or deployment failures retain evidence. Ambiguous deployment reconciles against revision identity and target URL. Rollback is a new approved revision/publication and must itself deploy and verify.
