# Policy registries

One governed revision model supports general, approval, and notification categories with stable
identity/key, organization and optional location/product scope, schema version, effective dates,
approval, and immutable active history. Documents are bounded declarative JSON; executable content,
secrets, and provider credentials are rejected.

Approval policies declare action, approver permission, minimum approvals, self-approval, and
material-edit invalidation. Phase 5 approval execution is not implemented. Notification policies
are stored for the later notification service; Phase 4 sends nothing.
