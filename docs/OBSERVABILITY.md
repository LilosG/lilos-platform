# Observability Architecture

LILOs uses one bounded telemetry contract for API, worker, scheduler, workflows, providers, notifications, AI, and publishing. Correlation and trace identifiers cross durable-job boundaries; bodies, credentials, personal data, drafts, and raw provider payloads never do. Metrics use a fixed low-cardinality label allowlist. Operational incidents, service heartbeats, and versioned SLOs are persisted at migration `20260803_0013`.

Telemetry export is provider-neutral. Production startup requires an immutable release identifier and HTTPS telemetry endpoint. Runtime controls remain the only maintenance/emergency control plane and can restrict but never grant access.
