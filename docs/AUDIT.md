# Audit-event foundation

## Purpose and boundary

`audit_events` stores durable business and security evidence for future platform and product
modules. Audit records are distinct from operational logs: logs may expire or be sampled, while
required audit history remains durable and append-only.

This foundation has no public or client-facing API. Callers use the typed audit service inside an
existing database transaction. Organization, location, user, workflow, product, integration, and
approval ownership models remain future work.

## Creation contract

Every write uses `AuditEventCreate` and records:

- a namespaced event type and action;
- one stable result (`succeeded`, `failed`, `denied`, `partially_succeeded`, or `cancelled`);
- an aware UTC `occurred_at` timestamp;
- one stable actor type (`user`, `service`, `workflow`, `system`, or `external_provider`);
- a required human-readable summary; and
- optional bounded identity, scope, resource, correlation, workflow, network, reason, error,
  approval, chain, and metadata fields.

`recorded_at` is assigned when PostgreSQL persists the record. `occurred_at` identifies when the
action happened and may be earlier. Event IDs are application-generated UUIDv4 values.

`organization_id` is a nullable UUID with an `ON DELETE RESTRICT` foreign key now that organization
is the platform's primary tenant boundary. `location_id` is also nullable and references
`locations.id` with `ON DELETE RESTRICT`. Actor, workflow execution, and approval values remain UUID
references without foreign keys until their owning tables exist.
`previous_audit_event_id` retains its restrictive self-reference.

Location audit metadata contains lifecycle, slug, type, primary, and version values; it excludes
addresses and contact data.

Industry creation and lifecycle events are global and therefore omit organization scope.
Organization industry-assignment events include `organization_id`. These events record industry
ID/key, state or assignment changes, and resulting versions where applicable, but never copy full
default-configuration or policy JSON into audit metadata.

Organization- and location-profile create/update events include their appropriate organization and
location scope, profile resource ID, operation, resulting version, and changed field names. They do
not include profile prose, services, claims, guidance, disclaimers, landmarks, references, or CTA
content. Profile records and audit evidence use one caller-owned transaction.

## Transaction contract

`AuditEventService.record(session, command)` uses the caller's existing SQLAlchemy `AsyncSession`.
It flushes but never commits independently. Successful owning transactions commit the audit event;
failed owning transactions roll it back. Validation and persistence failures propagate and are
never silently ignored.

The caller owns the decision about its transaction boundary. The default future policy for
state-changing platform operations is one atomic transaction containing both the business change
and its audit event. A caller that deliberately treats an audit failure as non-fatal must establish
that policy explicitly and safely, such as through an isolated savepoint; the audit service does not
swallow failures.

## Metadata policy

Metadata is optional JSONB for small structured context that does not justify dedicated columns. It
must not contain secrets, credentials, tokens, full provider payloads, raw stack traces, or
unrestricted personal data.

The enforced policy is:

- top-level JSON object only;
- no more than 16,384 serialized UTF-8 bytes;
- no more than five levels of nesting;
- no more than 50 entries in one object or array and 200 values overall;
- keys use 1–64 ASCII identifier characters;
- strings contain at most 1,024 characters;
- numbers are finite; and
- secret-bearing keys such as passwords, API keys, access or refresh tokens, authorization,
  cookies, credentials, and private keys are rejected at any depth.

Validation rebuilds every container, and the service normalizes again before model creation. A
caller retaining and mutating its original dictionary cannot change the persisted event.

## Deterministic retrieval and indexes

Repository reads are bounded to at most 100 records and ordered by `occurred_at DESC, id DESC`.
The UUID tie-breaker makes retrieval deterministic when multiple events share the same action time.
The initial indexes support:

- global chronological audit processing;
- future organization-scoped chronological lookup;
- correlation history;
- resource history; and
- previous-event chain traversal.

No production list endpoint or speculative cross-tenant query behavior is exposed in this packet.
Future authorization and tenant services must enforce scope before using audit retrieval.

Organization creation and lifecycle services record organization/resource IDs, correlation ID,
state, and version in the same transaction as the state change. They do not copy organization
contact details or other unrestricted personal data into audit metadata.

## Immutability controls

The application repository exposes append and controlled read operations only; it has no update or
delete method. PostgreSQL additionally installs `audit_events_append_only`, a statement trigger that
rejects `UPDATE`, `DELETE`, and `TRUNCATE`.

These controls protect ordinary application operations but do not make a database administrator
incapable of changing schema or disabling triggers. Production deployment must later apply
least-privilege database roles that grant the application insert/select access while withholding
update, delete, truncate, trigger-management, and schema-owner privileges. Corrections create a new
event linked through `previous_audit_event_id`; they never rewrite prior evidence.

## Retention and privacy

Audit events are long-term records under the platform specification. Detailed retention, legal
hold, privacy deletion, export, and tenant-access policies belong to their owning future packets.
Until then, callers must minimize metadata, prefer stable references over copied payloads, omit
source IP and user-agent information unless permitted, and never record secret material.
