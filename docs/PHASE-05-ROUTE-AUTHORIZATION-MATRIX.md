# Phase 5 Route Authorization Matrix

| Surface | Authentication | Permission | AAL | Scope | Availability |
|---|---|---|---|---|---|
| Workflow/run reads | bearer | `workflows.read` | aal1 | organization/location | production-capable service boundary |
| Workflow submission | bearer | `workflows.execute` | aal1 | organization/location | production-capable service boundary |
| Cancel/replay | bearer | `workflows.manage` | aal2 | organization | administration boundary |
| Schedule reads | bearer | `schedules.read` | aal1 | organization | production-capable service boundary |
| Schedule mutation | bearer | `schedules.manage` | aal2 | organization/location | administration boundary |
| Worker claim/outcome | worker runtime identity (future deployment boundary) | none exposed to clients | n/a | internal | not HTTP-mounted |

No arbitrary permission check, provider execution endpoint, or unauthenticated production route is added.
