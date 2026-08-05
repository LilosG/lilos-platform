# Production Secrets Inventory

Required secret classes are database credentials; authentication trust configuration; OAuth client credentials; provider access/refresh material held by the secret-store boundary; notification and AI provider credentials; GitHub/repository and artifact credentials; telemetry/alert credentials; backup encryption material; and deployment identities.

Values must be created in the approved secret manager, scoped per environment and service identity, rotated under provider policy, and revocable without source changes. Validation checks presence and access but never displays values. Database URLs, tokens, OAuth codes/state, signing material, secret references, and credential-bearing repository URLs are prohibited from logs, traces, metrics, audit metadata, frontend bundles, fixtures, and commits.

No production secret manager or values were available for this milestone; all production secret sign-offs remain pending.

## Render Blueprint variable names

Every Render service receives safe non-secret values from `lilos-production-runtime` and derives `LILOS_RELEASE` from its own `RENDER_GIT_COMMIT`. The Blueprint declares these value-less service variables with `sync: false`:

- API: `LILOS_DATABASE_URL`, `LILOS_MIGRATION_DATABASE_URL`, `LILOS_SUPABASE_AUTH_ISSUER`, `LILOS_SUPABASE_AUTH_JWKS_URL`, `LILOS_TELEMETRY_EXPORT_ENDPOINT`, `LILOS_GOOGLE_OAUTH_CLIENT_ID`, `LILOS_GOOGLE_OAUTH_CLIENT_SECRET`, `LILOS_GOOGLE_OAUTH_REDIRECT_URI`, `LILOS_SECRET_ENCRYPTION_KEY`.
- Worker and scheduler: `LILOS_DATABASE_URL`, `LILOS_SUPABASE_AUTH_ISSUER`, `LILOS_SUPABASE_AUTH_JWKS_URL`, `LILOS_TELEMETRY_EXPORT_ENDPOINT`.

The database URL must use the dedicated least-privilege Supabase application identity. The migration URL must use the separately approved migration identity and is available only to the API pre-deploy instance. Auth endpoints and telemetry destinations are treated as controlled production configuration even when they are not credentials. Notification, AI, repository, and alert credentials remain outside the Blueprint until their actual configuration contracts and approved secret references exist.

The Google OAuth client ID/secret/redirect URI and the provider-secret encryption key are scoped to the API service only: no code path today performs token refresh or dispatch from the worker or scheduler, so neither needs these values. If a future packet moves refresh or dispatch to the worker, `LILOS_SECRET_ENCRYPTION_KEY` must be added there too, using the byte-identical value already configured on the API — a different key on each service would make tokens encrypted by one unreadable by the other.
