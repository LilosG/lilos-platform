# Product registry

The immutable seeded registry contains `seo`, `gbp`, `reviews`, `content`, `insights`, `leads`, and
`automations`. Records declare owner module, product version, configuration/fact/integration/profile
requirements, approval-policy requirement, and runtime-control namespace. Registration is not
entitlement, readiness, activation, permission, or provider connectivity.

Run `npm run db:seed:administration` after migrations. The transaction is deterministic and
idempotent; any mismatch fails instead of rewriting catalog data.
