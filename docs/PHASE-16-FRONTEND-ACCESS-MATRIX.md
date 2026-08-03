# Phase 16 Frontend Access Matrix

| Workspace | Required server context |
|---|---|
| Organization overview | active membership + `organization.read` |
| Products | product read permission + entitlement; readiness/control shown separately |
| Administration | corresponding manage permission; AAL2 for privilege/security operations |
| Approvals | product approve permission + current policy/revision + required AAL |
| Audit | `audit.read`, organization scope |
| Insights | `insights.read`; no lead-level personal data |

Hidden navigation is never a security boundary.
