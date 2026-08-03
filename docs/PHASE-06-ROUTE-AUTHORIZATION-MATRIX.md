# Phase 6 Route Authorization Matrix

| Operation | Permission | AAL | Scope |
|---|---|---|---|
| Read event/delivery status | `notifications.read` | aal1 | organization |
| Manage templates/preferences | `notifications.manage` | aal2 | organization |
| Persist send intent | `notifications.send` | aal1 | organization/location |

Provider attempts are worker-only. No unauthenticated or generic template-execution endpoint exists.
