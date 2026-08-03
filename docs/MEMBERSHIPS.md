# Organization memberships

`organization_memberships` permanently maps one `user_profiles` record to one organization. The
pair is unique forever, including after revocation or expiry; memberships are never physically
deleted. A user may have memberships in multiple organizations. `membership_type` is immutable
classification only and never grants a permission.

States are `invited`, `active`, `suspended`, `revoked`, and `expired`. Approved transitions are
invited→active/revoked/expired, active→suspended/revoked, and suspended→active/revoked. Revoked and
expired are terminal. Lifecycle timestamps match state, successful changes increment `version`
once, and every change requires an expected version except token-locked invitation acceptance.

Organization lifecycle administration and runtime suppression follow ADR 0010. User deactivation
suppresses access without mutating membership. Membership reads remain available in all states and
always require organization scope. Cross-organization identifiers produce the same not-found result
as missing records.

Direct local/test membership creation and first-owner bootstrap are temporary guarded operations.
Production normally provisions membership through invitation acceptance; no hidden owner or
superuser is created.

Production-capable membership reads require `organization.members.manage`. Suspend, restore, and
revoke additionally require server-fixed AAL2. Before suspending or revoking an active owner, the
service locks the organization and qualifying owners and rejects the operation if it would remove
the final active organization-scoped owner. This continuity safeguard grants no permission and
does not bypass explicit denies.
