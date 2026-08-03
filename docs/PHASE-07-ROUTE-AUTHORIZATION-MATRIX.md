# Phase 7 Route Authorization Matrix

| Operation | Permission | AAL | Scope |
|---|---|---|---|
| Read providers/connections/health | `integrations.read` | aal1 | organization/location |
| Begin/complete connection | `integrations.connect` | aal2 | organization/location |
| Refresh/reconnect/disconnect | `integrations.manage` | aal2 | organization/location |

OAuth callbacks additionally require one-time state and exact redirect validation. No provider business-operation endpoint exists.
