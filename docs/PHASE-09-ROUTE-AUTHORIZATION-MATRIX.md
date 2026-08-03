# Phase 9 Route Authorization Matrix

| Route operation | Permission | AAL | Scope |
|---|---|---|---|
| Profile and health read | `gbp.read` | aal1 | location |
| Confirm mapping/write enablement | `gbp.connect` | aal2 | location |
| Synchronize | `gbp.sync` | aal1 | location |
| Propose profile change | `gbp.propose` | aal1 | location |
| Approve/reject revision | `gbp.approve` | aal2 | location |
| Reserve publication | `gbp.publish` | aal2 | location |
| Diagnostics | `gbp.diagnostics` | aal1 | location |

Entitlement, readiness, current approval, confirmed mapping, active connection, capability, and runtime controls remain additional server-side gates.
