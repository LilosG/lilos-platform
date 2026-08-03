# Integration and Connection Foundation

Phase 7 separates immutable provider capabilities from organization-owned connections. Optional location scope is enforced with a composite tenant foreign key. Connection state, granted capabilities, health, token expiry metadata, and credential references are stored; access and refresh token plaintext is not.

OAuth authorization state uses 256-bit random values, persists SHA-256 hashes only, expires after ten minutes, is organization-bound, redirect-exact, row-locked, and single use. PKCE material is a secret-store reference. Provider credentials are handled through the narrow `SecretStore` interface and injected adapters; logs, audits, APIs, and ordinary configuration never receive secret values. Refresh implementations must serialize on the connection row and fail closed. No real credentials, provider network dependency, or GBP operation is included.
