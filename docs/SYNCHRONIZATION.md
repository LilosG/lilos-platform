# Provider Synchronization Foundation

Phase 8 separates definitions, runs, checkpoints, observed provider snapshots, desired platform state, proposed change intent, approval, dispatch, verification, and unresolved conflict. Canonical normalization and hashing make diffs and idempotency deterministic. Provider observations retain `provider_observed` authority and never overwrite approved platform facts automatically.

Pull and push work executes as Phase 5 jobs through Phase 7 adapters. Push intent must commit before dispatch and requires active authentication/authorization, entitlement, readiness, runtime permission, applicable approval, an active capable connection, and an idempotency key. Ambiguous provider outcomes reconcile rather than replay blindly. Phase 6 may report authorized status events; it is not an alternate event bus.
