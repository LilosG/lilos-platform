# DNS and TLS Runbook

Record approved canonical frontend, API, and exact OAuth callback hosts. Configure staged DNS changes, certificate issuance and automated renewal, HTTPS redirects, canonical host handling, HSTS only after HTTPS validation, restrictive CORS, CSP, secure cookies where used, and no wildcard OAuth redirects or origins. Verify DNS from independent resolvers, certificate chain/expiry, callback exact-match behavior, frontend/API routing, renewal alert, and rollback records. DNS credentials and values are never committed. Domain authority and production names remain pending.
