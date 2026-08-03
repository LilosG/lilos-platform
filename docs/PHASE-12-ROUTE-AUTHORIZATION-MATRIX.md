# Phase 12 Route Authorization Matrix

| Operation | Permission | AAL | Scope |
|---|---|---|---|
| Read content/history | `content.read` | aal1 | organization/location |
| Create opportunities/briefs | `content.create` | aal1 | organization/location |
| Create revision | `content.edit` | aal1 | organization/location |
| Editorial/client decision | `content.approve` | aal2 | organization/location |
| Reserve publication | `content.publish` | aal2 | organization/location |
| Rollback | `content.rollback` | aal2 | organization/location |
| Manage repository targets | `content.manage_targets` | aal2 | organization |
