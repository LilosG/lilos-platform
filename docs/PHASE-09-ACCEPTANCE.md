# Phase 9 Acceptance

Migration `20260803_0006` establishes accounts, explicit location mappings, immutable normalized snapshots, grounded change revisions, and durable publication intent. The Google production adapter and deterministic contract share the same boundary. Supported fields are deliberately narrow. Authentication, authorization, AAL2 approval/publication, entitlement, readiness, policy, runtime controls, connection capability, idempotency, verification, reconciliation, and audit remain separate.

Offline contract validation covers current endpoints/scope, supported masks, deterministic normalization, health explanations, unsupported-field rejection, and duplicate snapshot/publication constraints. Live Google validation remains explicitly deferred until an approved Google project and merchant credentials are supplied. Existing Starlette/httpx warning remains unchanged. Phase 9 status: complete.
