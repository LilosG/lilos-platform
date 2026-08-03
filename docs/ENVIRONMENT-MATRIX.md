# Environment Matrix

Local and test allow deterministic adapters and explicitly enabled bootstrap routes. Development and staging prohibit bootstrap routes and use non-production identities, databases, credentials, callbacks, recipients, and telemetry. Production additionally requires an immutable `LILOS_RELEASE`, HTTPS authentication endpoints, a telemetry export endpoint, PostgreSQL, and disabled internal routes.

Production data and secrets must never flow into lower environments. Provider sandbox/test resources must remain separate from live resources. The production preflight validates required names without printing values; environment ownership, retention, capacity, and access approvals remain deployment sign-off items.

For production, Vercel serves Astro, Supabase Oregon owns PostgreSQL/Auth, and Render Oregon owns only `lilos-api`, `lilos-worker`, and `lilos-scheduler`. The Render environment group commits safe constants (`production`, log level, API version, sampling, timeouts, disabled internal routes, audience, and algorithms). Release identity is derived per service from Render's immutable `RENDER_GIT_COMMIT`. Database, migration, authentication endpoint, and telemetry values are dashboard-supplied `sync: false` variables.
