# Phase 11 Route Authorization Matrix

| Operation | Permission | AAL | Scope |
|---|---|---|---|
| List/read minimized lead records | `leads.read` | aal1 | organization/location |
| Plan eligible communication | `leads.respond` | aal1 | organization/location |
| Route/assign | `leads.assign` | aal1 | organization/location |
| Manage verified sources/intake | `leads.manage_sources` | aal2 | organization |
| Record consent/withdrawal/suppression | `leads.manage_consent` | aal2 | organization/lead |
