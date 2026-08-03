# Phase 4 route authorization matrix

All routes are always-mounted under `/api/v1/organizations/{organization_id}`, require bearer
identity, active organization/membership, fixed server permission, organization scope, correlation
ID, and `Cache-Control: no-store`. Location IDs receive same-organization validation.

| Surface | Permission | Minimum AAL | Notes |
| --- | --- | --- | --- |
| services/assignments | `services.read` / `.manage` | aal1; archive aal2 | Scoped records |
| business facts | `business_facts.read` / `.propose` / `.approve` | approval aal2 | Missing/conflict explicit |
| products/readiness | `products.read` | aal1 | Registry read-only |
| entitlements | `products.entitlements.manage` | aal2 | Activation checks readiness |
| configuration | `configuration.read` / `.manage` | activation aal2 | Registered schema only |
| policies | `policies.read` / `.manage` | activation aal2 | Declarative only |
| feature flags | `feature_flags.read` / `.manage` | aal1 | Cannot grant access |
| runtime controls | `runtime_controls.read` / `.manage` | mutation aal2 | Restrictive only |
| onboarding | `onboarding.read` / `.manage` | aal1 | Evidence required |
| offboarding | `offboarding.manage` | aal2 | No destructive execution |

No generic permission check, schema/product creation, cross-tenant listing, or client-controlled
policy endpoint exists. Phase 4 catalog creation uses explicit seed commands, not routes.
