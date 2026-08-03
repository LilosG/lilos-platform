# Organization invitations

Invitation creation atomically creates one invited membership. The record stores normalized
casefolded email, a SHA-256 token digest, expiry, lifecycle timestamps, actors, and version. It never
stores plaintext. Tokens contain 32 random bytes encoded URL-safe without padding. The guarded
local/test creation route returns plaintext once with `Cache-Control: no-store` and `Pragma:
no-cache`; it cannot be retrieved later and must never enter logs or audit events.

Pending invitations accept, cancel, or expire. Acceptance requires the existing authentication
boundary, an active mapped platform user, and exact match against normalized `user_profiles.email`.
JWT email is not used. Acceptance locks the invitation and membership, then atomically accepts and
activates them. Replay permits one success. Cancellation revokes the invited membership. Dynamic
expiry expires both records and persists audit evidence. Invalid, mismatched, expired, cancelled,
accepted, replayed, and unknown tokens use the same non-enumerating failure.

The default lifetime is seven days and the maximum is thirty. Only one pending invitation per
organization/email is allowed. Resend means cancel and create a new invitation; token rotation is
not implemented. Production email delivery is deferred and no provider management API is used.
