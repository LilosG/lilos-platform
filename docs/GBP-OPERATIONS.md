# GBP Operations Runbook

Connection failures require reconnect; never expose provider errors verbatim. Stale discovery or sync is rerun idempotently. A timeout after PATCH is ambiguous: do not retry; enqueue reconciliation, reread the masked fields, and mark verified only on an exact match. A mismatch retains both expected and observed state. Emergency provider-write controls stop dispatch but do not alter authorization or approval.
