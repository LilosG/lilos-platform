# API runtime contract

## Scope

The FastAPI application in `apps/api` is the HTTP boundary of the LILOs modular monolith. The
current runtime exposes health, generated OpenAPI documentation, and conditionally registered
temporary organization bootstrap routes. Product APIs, authentication, queues, and external
providers are not implemented. The shared audit service is an internal transactional capability;
there is no production audit-list or audit-write API.

OpenAPI is available locally at `/openapi.json`, with Swagger UI at `/docs` and ReDoc at `/redoc`.

## Runtime settings

Settings are validated during application creation. The supported environment names are:

- `local`
- `test`
- `development`
- `staging`
- `production`

The runtime recognizes these variables:

- `LILOS_ENV`
- `LILOS_LOG_LEVEL`
- `LILOS_API_TITLE`
- `LILOS_API_VERSION`
- `LILOS_DATABASE_URL`
- `LILOS_DATABASE_CONNECT_TIMEOUT_SECONDS`
- `LILOS_INTERNAL_ADMIN_ROUTES_ENABLED`
- `LILOS_MIGRATION_DATABASE_URL`
- `LILOS_TEST_DATABASE_URL`

Values may come from process environment variables or a local, ignored `.env` file. Environment
variables take precedence. Empty values in `.env.example` are ignored so safe defaults remain
usable. Invalid environment names, log levels, or metadata fail settings validation.

`LILOS_INTERNAL_ADMIN_ROUTES_ENABLED` defaults to false. It may be true only with `LILOS_ENV=local`
or `test`; development, staging, and production reject unsafe enablement during settings validation.

## Correlation IDs

The request and response header is `X-Correlation-ID`.

An incoming value is accepted only when it is 1–64 ASCII characters and matches:

```text
^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$
```

This excludes whitespace, control characters, non-ASCII text, and unbounded values. If the header
is absent or invalid, the API generates a canonical lowercase UUIDv4. The resolved value is:

- returned in the `X-Correlation-ID` response header;
- included in response-envelope metadata when the response has an API body;
- available to handlers as `request.state.correlation_id`; and
- bound to request-scoped structured application logging.

## Success contracts

`GET /health/live` reports only that the API process is running:

```json
{
  "data": {
    "service": "lilos-api",
    "status": "alive"
  },
  "meta": {
    "correlation_id": "d67dc931-cc59-4d9d-aa02-f6531803a8f4"
  }
}
```

`GET /health/ready` reports whether PostgreSQL is available for database-backed work. When healthy:

```json
{
  "data": {
    "service": "lilos-api",
    "status": "ready",
    "dependencies": [
      {
        "name": "postgresql",
        "status": "healthy"
      }
    ]
  },
  "meta": {
    "correlation_id": "d67dc931-cc59-4d9d-aa02-f6531803a8f4"
  }
}
```

When configuration is absent or connectivity fails, readiness returns HTTP 503 with `not_ready` and
the PostgreSQL status `unavailable`. The response never includes credentials, hostnames, database
names, exception details, or raw driver errors. Liveness never opens a database connection.

## Error contract

All handled API errors use this envelope:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "The request did not pass validation.",
    "category": "validation",
    "retryable": false,
    "details": [
      {
        "field": "body.name",
        "code": "missing",
        "message": "Field required"
      }
    ]
  },
  "meta": {
    "correlation_id": "d67dc931-cc59-4d9d-aa02-f6531803a8f4"
  }
}
```

Current stable mappings are:

| HTTP status | Code                      | Category         |
| ----------- | ------------------------- | ---------------- |
| 401         | `AUTHENTICATION_REQUIRED` | `authentication` |
| 403         | `PERMISSION_DENIED`       | `authorization`  |
| 404         | `RESOURCE_NOT_FOUND`      | `not_found`      |
| 409         | `RESOURCE_CONFLICT`       | `conflict`       |
| 422         | `VALIDATION_FAILED`       | `validation`     |
| 500         | `INTERNAL_SERVER_ERROR`   | `system`         |
| 503         | `DATABASE_UNAVAILABLE`    | `system`         |

Organization bootstrap routes additionally use stable `ORGANIZATION_NOT_FOUND`,
`ORGANIZATION_SLUG_CONFLICT`, `ORGANIZATION_VERSION_CONFLICT`, and
`ORGANIZATION_TRANSITION_CONFLICT` codes with the same standard envelope.
Industry routes use `INDUSTRY_NOT_FOUND`, `INDUSTRY_KEY_CONFLICT`,
`INDUSTRY_VERSION_CONFLICT`, `INDUSTRY_TRANSITION_CONFLICT`, and
`INDUSTRY_ASSIGNMENT_CONFLICT`.
Profile routes use `ORGANIZATION_PROFILE_NOT_FOUND`, `ORGANIZATION_PROFILE_CONFLICT`,
`ORGANIZATION_PROFILE_VERSION_CONFLICT`, `LOCATION_PROFILE_NOT_FOUND`,
`LOCATION_PROFILE_CONFLICT`, `LOCATION_PROFILE_VERSION_CONFLICT`, and
`PROFILE_PARENT_STATE_CONFLICT`.
Location-group routes use `LOCATION_GROUP_NOT_FOUND`, `LOCATION_GROUP_KEY_CONFLICT`,
`LOCATION_GROUP_VERSION_CONFLICT`, `LOCATION_GROUP_STATE_CONFLICT`,
`LOCATION_GROUP_PARENT_STATE_CONFLICT`, `LOCATION_GROUP_LOCATION_STATE_CONFLICT`,
`LOCATION_GROUP_MEMBERSHIP_CONFLICT`, and `LOCATION_GROUP_MEMBERSHIP_NOT_FOUND`.

Validation details contain safe field locations, stable validation types, and messages. Submitted
values and validator exception context are omitted. Unexpected errors return a generic message;
stack traces, exception messages, secrets, and internal implementation details are not returned to
clients.

## Temporary organization bootstrap routes

When explicitly enabled in local or test, these routes are registered:

- `POST /internal/organizations`
- `GET /internal/organizations/{organization_id}`
- `GET /internal/organizations?limit=50&offset=0`
- `POST /internal/organizations/{organization_id}/start-onboarding`
- `POST /internal/organizations/{organization_id}/activate`
- `POST /internal/organizations/{organization_id}/pause`
- `POST /internal/organizations/{organization_id}/resume`
- `POST /internal/organizations/{organization_id}/suspend`
- `POST /internal/organizations/{organization_id}/start-offboarding`
- `POST /internal/organizations/{organization_id}/archive`
- `POST /internal/organizations/{organization_id}/industry`

Lifecycle request bodies contain `expected_version`. Success bodies use `data` plus correlation
metadata; collection bodies also include bounded deterministic pagination metadata. These routes
are unauthenticated temporary bootstrap surfaces, are absent by default, and must not be treated as
production-safe administration APIs.

## Temporary location bootstrap routes

The same local/test-only guard registers organization-scoped location create, list, get, and
lifecycle routes below `/internal/organizations/{organization_id}/locations`. Lifecycle suffixes
are `activate`, `pause`, `close-temporarily`, `close-permanently`, and `archive`; every mutation
accepts `{"expected_version": <integer>}`. No global location route exists. Cross-organization IDs
return the same `LOCATION_NOT_FOUND` response as missing IDs.

Stable conflicts are `LOCATION_SLUG_CONFLICT`, `LOCATION_PRIMARY_CONFLICT`,
`LOCATION_PARENT_STATE_CONFLICT`, `LOCATION_VERSION_CONFLICT`, and
`LOCATION_TRANSITION_CONFLICT`. These remain temporary unauthenticated bootstrap surfaces.

## Temporary industry bootstrap routes

The same local/test-only guard registers:

- `POST /internal/industries`
- `GET /internal/industries?limit=50&offset=0`
- `GET /internal/industries/{industry_id}`
- `POST /internal/industries/{industry_id}/deprecate`
- `POST /internal/industries/{industry_id}/reactivate`
- `POST /internal/industries/{industry_id}/archive`

Lifecycle request bodies require `expected_version`. Industry policy bodies use bounded,
secret-key-rejecting JSON objects documented in `docs/INDUSTRIES.md`. These routes and the
organization industry-assignment route remain unauthenticated temporary bootstrap surfaces and
are absent by default.

## Temporary profile bootstrap routes

The same local/test-only guard registers separate controlled profile surfaces:

- `POST`, `GET`, and `PUT /internal/organizations/{organization_id}/profile`
- `POST`, `GET`, and `PUT /internal/organizations/{organization_id}/locations/{location_id}/profile`

`PUT` is a typed full replacement and requires `expected_version`. Location routes always include
organization scope. Profiles are returned separately; no effective-profile composition API or AI
write route exists. Parent lifecycle permissions and content limits are documented in
`docs/PROFILES.md`. These are temporary unauthenticated bootstrap routes and are absent by default.

## Temporary location-group bootstrap routes

The local/test-only guard also registers organization-scoped location-group create, list, get,
replace, and archive routes below
`/internal/organizations/{organization_id}/location-groups`. Membership list, add, and remove use
`/{group_id}/locations` and `/{group_id}/locations/{location_id}`. Lists use bounded offset
pagination ordered by `created_at ASC, id ASC`.

There is no global group route, nested-group route, bulk mutation, configuration behavior, or
frontend. The surfaces are unauthenticated bootstrap routes, absent by default, and not
production-safe. See `docs/LOCATION-GROUPS.md`.

## Temporary business-identity read routes

The same guard registers two read-only current-context routes:

- `GET /internal/organizations/{organization_id}/business-identity`
- `GET /internal/organizations/{organization_id}/locations/{location_id}/business-identity`

Responses are immutable typed read models with correlation metadata. Missing profiles and legacy
missing industries are explicit; no default is fabricated. Location resolution includes
organization scope and preserves ordinary not-found behavior for a wrong-owner location. Lists and
claims remain separated by profile source, and only the explicitly named CTA override is resolved.
See `docs/BUSINESS-IDENTITY.md` and ADR 0008.

## Temporary authentication and user-profile routes

With the existing local/test-only internal guard enabled, the API registers `GET
/internal/auth/me` plus create, get, deactivate, and reactivate routes below
`/internal/user-profiles`. `/internal/auth/me` accepts only a bounded bearer access token and
returns the minimal principal documented in `docs/AUTHENTICATION.md`; it never returns email or
organization scope. Identity responses use `Cache-Control: no-store`.

Authentication failures use generic `401 AUTHENTICATION_REQUIRED` with `WWW-Authenticate: Bearer`.
Unavailable JWKS verification uses retryable `503 AUTHENTICATION_UNAVAILABLE`. Both retain the
standard error envelope and correlation ID without echoing token or account data. These routes are
unregistered by default and are temporary bootstrap/diagnostic surfaces, not production-safe
authorization.

## Logging

LILOs application logs are emitted as one JSON object per line. The base record includes timestamp,
severity, environment, service, deployment version, event name, message, and correlation ID.
Request completion records add method, route, status code, duration, and outcome. Request and
response bodies, query strings, credentials, and submitted validation values are not logged by
default. Database failures log normalized codes and exception types without URLs or raw driver
messages.

## Temporary membership and access bootstrap routes

The local/test-only guard registers organization-scoped membership, invitation, role-assignment,
permission-deny, fixed-catalog-read, and first-owner bootstrap routes. Invitation creation returns
plaintext once with `Cache-Control: no-store` and `Pragma: no-cache`; it is absent from later reads,
logs, and audit events. Acceptance requires the existing bearer-authenticated principal.

The router is absent by default and rejected in development, staging, and production. These routes
do not authorize existing APIs. JWT organization/role claims are ignored, and authentication alone
grants no organization access. See `docs/MEMBERSHIPS.md`, `docs/INVITATIONS.md`, and
`docs/AUTHORIZATION-MODEL.md`.
