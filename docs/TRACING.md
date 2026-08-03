# Tracing Standard

Inbound requests create correlation, trace, and span identifiers. Authentication, authorization, transactions, workflow submission, jobs, adapters, delivery, verification, and reconciliation create child spans. Durable jobs persist only bounded identifiers. Sampling is configured by `LILOS_TRACE_SAMPLE_RATE`; bodies and secrets are never captured.
