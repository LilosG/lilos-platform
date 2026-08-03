# Frontend Architecture

The Astro application consumes typed API contracts only. Session bootstrap, membership selection, organization/location context, permission policy, entitlement, readiness, feature flags, lifecycle, and runtime controls originate from server responses; local visibility never grants access. Tokens and secrets are not persisted in local storage. Every critical state has explicit loading, empty, blocked, degraded, unauthorized, not-found, stale, conflict, and step-up guidance.
