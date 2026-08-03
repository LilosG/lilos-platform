# Phase 14 Route Authorization Matrix

| Surface | Permission | AAL |
|---|---|---:|
| Capabilities, completeness, performance, alerts | `gbp.read` | aal1 |
| Proposals and schedules | `gbp.propose` | aal1 |
| Primary category, hours, media, posts, change-set approval | `gbp.approve` | aal2 |
| Provider dispatch, cancellation, reconciliation | `gbp.publish` | aal2 |

All scopes are organization/location validated and unsupported capabilities fail closed.
