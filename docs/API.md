# API runtime contract

## Scope

The FastAPI application in `apps/api` is the HTTP boundary of the LILOs modular monolith. The
current runtime exposes health and generated OpenAPI documentation only. Product APIs,
authentication, queues, and external providers are not implemented. The shared audit service is an
internal transactional capability; this packet exposes no production audit-list or audit-write API.

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
- `LILOS_MIGRATION_DATABASE_URL`
- `LILOS_TEST_DATABASE_URL`

Values may come from process environment variables or a local, ignored `.env` file. Environment
variables take precedence. Empty values in `.env.example` are ignored so safe defaults remain
usable. Invalid environment names, log levels, or metadata fail settings validation.

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

| HTTP status | Code | Category |
| --- | --- | --- |
| 401 | `AUTHENTICATION_REQUIRED` | `authentication` |
| 403 | `PERMISSION_DENIED` | `authorization` |
| 404 | `RESOURCE_NOT_FOUND` | `not_found` |
| 409 | `RESOURCE_CONFLICT` | `conflict` |
| 422 | `VALIDATION_FAILED` | `validation` |
| 500 | `INTERNAL_SERVER_ERROR` | `system` |
| 503 | `DATABASE_UNAVAILABLE` | `system` |

Validation details contain safe field locations, stable validation types, and messages. Submitted
values and validator exception context are omitted. Unexpected errors return a generic message;
stack traces, exception messages, secrets, and internal implementation details are not returned to
clients.

## Logging

LILOs application logs are emitted as one JSON object per line. The base record includes timestamp,
severity, environment, service, deployment version, event name, message, and correlation ID.
Request completion records add method, route, status code, duration, and outcome. Request and
response bodies, query strings, credentials, and submitted validation values are not logged by
default. Database failures log normalized codes and exception types without URLs or raw driver
messages.
