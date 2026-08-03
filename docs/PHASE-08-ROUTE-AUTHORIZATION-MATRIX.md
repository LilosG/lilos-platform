# Phase 8 Route Authorization Matrix

| Operation | Permission | AAL | Scope |
|---|---|---|---|
| Read runs/checkpoints/conflicts | `synchronization.read` | aal1 | organization/location |
| Persist pull/push intent | `synchronization.execute` | aal2 | organization/location |
| Retry/reconcile/cancel | `synchronization.manage` | aal2 | organization/location |

Permissions are server-fixed. Provider callbacks and worker dispatch are internal adapter surfaces, not generic client APIs.
