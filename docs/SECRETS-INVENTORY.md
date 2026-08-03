# Production Secrets Inventory

Required secret classes are database credentials; authentication trust configuration; OAuth client credentials; provider access/refresh material held by the secret-store boundary; notification and AI provider credentials; GitHub/repository and artifact credentials; telemetry/alert credentials; backup encryption material; and deployment identities.

Values must be created in the approved secret manager, scoped per environment and service identity, rotated under provider policy, and revocable without source changes. Validation checks presence and access but never displays values. Database URLs, tokens, OAuth codes/state, signing material, secret references, and credential-bearing repository URLs are prohibited from logs, traces, metrics, audit metadata, frontend bundles, fixtures, and commits.

No production secret manager or values were available for this milestone; all production secret sign-offs remain pending.
