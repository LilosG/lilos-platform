# Phase 17 Route Authorization Matrix

| Surface | Authentication | Permission | AAL | Availability |
|---|---|---|---|---|
| Health liveness/readiness | No | None | — | All environments; non-sensitive |
| Operator diagnostics | Required | runtime_controls.read | aal2 | Not mounted until operator identity is approved |
| Incident administration | Required | runtime_controls.manage | aal2 | Service contract; production mounting deferred |
| Maintenance/emergency controls | Required | runtime_controls.manage | aal2 | Existing runtime-control service |

No generic telemetry, arbitrary metric, or customer-visible incident-detail endpoint exists.
