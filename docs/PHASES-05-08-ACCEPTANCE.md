# Workflow, Notification, Integration, and Provider Foundation Acceptance

Phases 5–8 form one layered foundation with four independent commit/migration boundaries: durable execution (`20260803_0002`), notification delivery intent (`20260803_0003`), secure connections (`20260803_0004`), and provider synchronization (`20260803_0005`).

The milestone preserves tenant ownership, caller-owned transactions, audit compatibility, authorization/AAL separation, entitlement/readiness/runtime/approval gates, commit-before-side-effect, deterministic idempotency, hash-only OAuth state, opaque secret references, and provider-authority isolation. It contains no real credentials, provider calls, duplicate queue, production notification provider, or GBP operation.

Acceptance: durable crash recovery and bounded retry; deduplicated notification delivery; secure one-time OAuth intents; serialized refresh boundary; deterministic checkpoints/diffs; explicit conflicts; durable pre-dispatch intent; no cross-tenant ownership; reversible migration chain; separate permission catalog additions; focused acceptance documents. Known warning: the unchanged Starlette/httpx compatibility warning. Milestone status: complete.
