# Phase 3 route authorization matrix

All `/api/v1` routes are always mounted, bearer-authenticated, no-store, and evaluated against the
current active organization and membership. Permission keys and AAL requirements are fixed in
server code. `org` means organization scope; `loc` means the named location scope. Child-resource
lookups preserve not-found equivalence when the identifier belongs to another organization.

## Production-capable routes (classification A)

| Method | Route | Scope | Permission | AAL | Service | Not-found equivalence |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/organizations/{organization_id}` | org | `organization.read` | aal1 | Organization | n/a |
| POST | `.../{organization_id}/pause` | org | `organization.update` | aal1 | Organization | n/a |
| POST | `.../{organization_id}/suspend` | org | `organization.update` | aal1 | Organization | n/a |
| POST | `.../{organization_id}/start-offboarding` | org | `organization.update` | aal1 | Organization | n/a |
| POST | `.../{organization_id}/industry` | org | `organization.settings.manage` | aal1 | Organization | n/a |
| POST | `.../{organization_id}/locations` | org | `locations.create` | aal1 | Location | yes, parent |
| GET | `.../{organization_id}/locations` | org | `locations.read` | aal1 | Location | yes |
| GET | `.../{organization_id}/locations/{location_id}` | loc | `locations.read` | aal1 | Location | yes |
| POST | `.../locations/{location_id}/{activate,pause,close-temporarily,close-permanently,archive}` | loc | `locations.lifecycle.manage` | aal1 | Location | yes |
| POST | `.../{organization_id}/profile` | org | `profiles.update` | aal1 | Organization profile | yes |
| GET | `.../{organization_id}/profile` | org | `profiles.read` | aal1 | Organization profile | yes |
| PUT | `.../{organization_id}/profile` | org | `profiles.update` | aal1 | Organization profile | yes |
| POST | `.../locations/{location_id}/profile` | loc | `profiles.update` | aal1 | Location profile | yes |
| GET | `.../locations/{location_id}/profile` | loc | `profiles.read` | aal1 | Location profile | yes |
| PUT | `.../locations/{location_id}/profile` | loc | `profiles.update` | aal1 | Location profile | yes |
| GET | `.../{organization_id}/business-identity` | org | `business_identity.read` | aal1 | Business identity | yes |
| GET | `.../locations/{location_id}/business-identity` | loc | `business_identity.read` | aal1 | Business identity | yes |
| POST | `.../{organization_id}/location-groups` | org | `locations.groups.manage` | aal1 | Location group | yes |
| GET | `.../{organization_id}/location-groups` | org | `locations.read` | aal1 | Location group | yes |
| GET | `.../location-groups/{group_id}` | org | `locations.read` | aal1 | Location group | yes |
| PUT | `.../location-groups/{group_id}` | org | `locations.groups.manage` | aal1 | Location group | yes |
| POST | `.../location-groups/{group_id}/archive` | org | `locations.groups.manage` | aal1 | Location group | yes |
| GET | `.../location-groups/{group_id}/locations` | org | `locations.read` | aal1 | Location group | yes |
| POST | `.../location-groups/{group_id}/locations/{location_id}` | org | `locations.groups.manage` | aal1 | Location group | yes |
| DELETE | `.../location-groups/{group_id}/locations/{location_id}` | org | `locations.groups.manage` | aal1 | Location group | yes |
| GET | `.../{organization_id}/memberships/{membership_id}` | org | `organization.members.manage` | aal1 | Access control | yes |
| POST | `.../memberships/{membership_id}/{suspend,restore,revoke}` | org | `organization.members.manage` | aal2 | Access control | yes |
| GET | `.../{organization_id}/invitations/{invitation_id}` | org | `organization.invitations.manage` | aal1 | Access control | yes |
| POST | `.../invitations/{invitation_id}/cancel` | org | `organization.invitations.manage` | aal2 | Access control | yes |
| POST | `/api/v1/invitations/accept` | token scope | authenticated recipient | aal1 | Access control | generic failure |
| POST | `.../memberships/{membership_id}/role-assignments` | org | `organization.roles.manage` | aal2 | Access control | yes |
| DELETE | `.../role-assignments/{assignment_id}` | org | `organization.roles.manage` | aal2 | Access control | yes |
| POST | `.../memberships/{membership_id}/permission-denies` | org | `organization.roles.manage` | aal2 | Access control | yes |
| DELETE | `.../permission-denies/{deny_id}` | org | `organization.roles.manage` | aal2 | Access control | yes |
| GET | `.../{organization_id}/access/roles` | org | `organization.roles.manage` | aal1 | Catalog repository | n/a |
| GET | `.../{organization_id}/access/permissions` | org | `organization.roles.manage` | aal1 | Catalog repository | n/a |

Organization activation/resumption and reads in non-active lifecycle states cannot use the general
runtime evaluator, which intentionally admits only active organizations. Those administrative
recovery operations remain contained in local/test bootstrap pending a platform-administration
permission model. Domain services still decide whether every listed lifecycle mutation is valid.

## Guarded bootstrap and diagnostics (classifications B and D)

The following routes register only when `LILOS_INTERNAL_ADMIN_ROUTES_ENABLED=true` and the
environment is local/test. They are absent in development, staging, and production.

| Route family | Classification | Reason retained | Authentication |
| --- | --- | --- | --- |
| `/internal/industries...` | B | deterministic global registry setup/lifecycle | bootstrap guard |
| `/internal/organizations...` | B | create tenant, reach initial active state, recovery testing | bootstrap guard |
| `/internal/.../locations...` | B | deterministic domain fixture setup | bootstrap guard |
| `/internal/.../profile` | B | deterministic controlled-profile fixtures | bootstrap guard |
| `/internal/.../location-groups...` | B | deterministic group fixtures | bootstrap guard |
| `/internal/.../business-identity` | D | local computed-read diagnostic | bootstrap guard |
| `/internal/auth/me` | D | local verifier/principal diagnostic | bearer authentication |
| `/internal/user-profiles...` | B | no safe global platform-admin permission exists | bootstrap guard |
| `POST /internal/.../memberships` | B | direct fixture membership creation | bootstrap guard |
| `POST /internal/.../bootstrap-owner` | B | first local/test owner only | bootstrap guard |
| `POST /internal/.../invitations` | B | one-time plaintext until production delivery exists | bearer + permission + aal2 |

Health endpoints `/health/live` and `/health/ready` are classification C operational routes and do
not expose organization data. OpenAPI documentation is framework operational surface. The five
proof-only `/internal/.../authorization-test` routes are classification E and were removed. There
is no global organization list, user list, audit browser, arbitrary permission-check route, or
production-mounted unauthenticated bootstrap route.
