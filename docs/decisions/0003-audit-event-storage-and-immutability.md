# ADR 0003: Audit-event storage and immutability

- Status: Accepted
- Date: 2026-08-01
- Owners: Platform Engineering
- Related roadmap phase: Phase 1

## Context

Every future platform and product module needs one shared audit capability. The initial table must
support stable actor and result values, nullable references to domains that do not yet exist,
bounded structured metadata, deterministic retrieval, and append-only behavior without creating
tenant or product tables prematurely.

## Decision

Store audit events in one PostgreSQL `audit_events` table owned by the shared audit module. Store
actor and result values as bounded strings with named `CHECK` constraints rather than native
PostgreSQL enum types. This preserves database enforcement while allowing a future additive enum
value through an ordinary constraint migration instead of a database-type lifecycle.

Use JSONB only for small validated metadata that is not a relational identity or primary lookup
field. Important identity, scope, chronology, result, correlation, and resource values remain typed
columns.

Enforce ordinary append-only behavior at two layers: the repository exposes no update or delete
operations, and a PostgreSQL trigger rejects update, delete, and truncate statements. Future
production roles must additionally withhold mutation and schema-owner privileges from the
application identity.

## Consequences

- Future modules share one typed write contract and transactional service.
- Audit writes can be atomic with their owning platform change.
- Unknown actor and result values fail in both Pydantic and PostgreSQL.
- Nullable UUID references avoid fake owner tables and premature foreign keys.
- A self-reference supports correction or causation chains without rewriting history.
- The trigger protects against mutation through a general application session, but privileged
  database administrators retain emergency schema authority that must be governed operationally.
- Adding an enum value requires a version-controlled check-constraint migration.

## Alternatives considered

- Native PostgreSQL enums: rejected for this foundation because constrained strings provide equal
  current integrity with a simpler additive migration lifecycle.
- Repository-only append behavior: rejected because a general ORM session or direct SQL could
  bypass it.
- Database roles only: deferred to deployment because production roles and provisioning are outside
  this packet; the required future grant policy is documented.
- One audit table per product: rejected because audit is a shared platform capability.
- Unbounded JSONB state snapshots: rejected because they increase privacy, secret, retention, and
  query risks.

## Validation and review

Validate contracts, metadata policy, transaction rollback, deterministic reads, schema constraints,
indexes, foreign keys, migration movement, and database rejection of update, delete, and truncate.
Review this decision when production database roles, retention policy, tenant authorization, or
audit export are implemented.
