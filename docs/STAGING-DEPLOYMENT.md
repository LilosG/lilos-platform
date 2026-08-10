# Governed Render Staging Deployment

`render.staging.yaml` is the smallest permanent non-production projection required for Packet 2
live acceptance. It reuses the production Docker image and start/predeploy scripts, but creates an
independent protected Render environment containing only:

- `lilos-staging-api` (Starter web service);
- `lilos-staging-worker` (Starter background worker); and
- `lilos-staging-postgres` (private PostgreSQL 17, Basic 256 MB, 15 GB).

The scheduler is deliberately excluded because Packet 2 invokes workflows through the API and
requires the durable worker, not periodic schedule acceptance. Add a staging scheduler only when a
scheduled-execution acceptance scope is approved. The root `render.yaml` remains the production
projection and is not used to provision staging.

## Safety invariants

- The Blueprint path is `render.staging.yaml`, linked to
  `worker/backend-closure-2026-08-10`.
- Both services track that same branch, have automatic deploys disabled, and must be manually
  deployed from the same immutable commit.
- `lilos-staging-postgres` is created inside the protected, network-isolated `staging` environment.
  Its public inbound allow list is empty. Both application and migration URLs reference its private
  Render connection string.
- Only the API runs `sh /app/scripts/render_predeploy.sh`; the worker never migrates. Predeploy runs
  `alembic upgrade head` and the established idempotent catalog seeds.
- Internal administration bootstrap routes remain disabled.
- `LILOS_PROVIDER_WRITES_ENABLED=false` is committed as a safe staging constant. Every real GBP,
  Reviews, and GitHub publication handler fails with `PROVIDER_WRITES_DISABLED` before its provider
  write unless an operator deliberately opens an approved write window.
- No production database URL, authentication project, provider application, encryption key,
  telemetry endpoint, token, or application secret may be reused.

## External inventory prerequisite

The CLI token available during preparation was expired. An authorized Render operator must first
run:

```sh
render login
render whoami
render services --include-previews --output json
render postgres list --output json
render projects --output json
```

If existing resources named `lilos-staging-api`, `lilos-staging-worker`, or
`lilos-staging-postgres` appear, stop and determine whether they are already governed by a
Blueprint. Never attach a resource managed by another Blueprint. If an existing environment meets
every invariant in this document, use its service IDs and do not create duplicates.

## One-time Blueprint provisioning

In the Render Dashboard, select **New > Blueprint** and use exactly:

- Blueprint name: `lilos-platform-staging`
- repository: the LILOs platform repository
- linked branch: `worker/backend-closure-2026-08-10`
- Blueprint Path: `render.staging.yaml`

Review the plan before applying it. It must contain one project/environment, one PostgreSQL
database, and the two services listed above. It must not update `lilos-api`, `lilos-worker`,
`lilos-scheduler`, or any production datastore or environment group.

Render prompts for the following service placeholders during initial Blueprint creation. Supply
new staging-only values; names are listed here intentionally, values must remain in Render's secret
configuration.

`lilos-staging-api`:

- `LILOS_SUPABASE_AUTH_ISSUER`
- `LILOS_SUPABASE_AUTH_JWKS_URL`
- `LILOS_TELEMETRY_EXPORT_ENDPOINT`
- `LILOS_WEB_ORIGINS`
- `LILOS_GOOGLE_OAUTH_CLIENT_ID`
- `LILOS_GOOGLE_OAUTH_CLIENT_SECRET`
- `LILOS_GOOGLE_OAUTH_REDIRECT_URI`
- `LILOS_SECRET_ENCRYPTION_KEY`
- `LILOS_GITHUB_APP_ID`
- `LILOS_GITHUB_APP_CLIENT_ID`
- `LILOS_GITHUB_APP_PRIVATE_KEY`
- `LILOS_GITHUB_APP_INSTALLATION_REDIRECT_URI`

`lilos-staging-worker`:

- `LILOS_SUPABASE_AUTH_ISSUER`
- `LILOS_SUPABASE_AUTH_JWKS_URL`
- `LILOS_TELEMETRY_EXPORT_ENDPOINT`
- `LILOS_GOOGLE_OAUTH_CLIENT_ID`
- `LILOS_GOOGLE_OAUTH_CLIENT_SECRET`
- `LILOS_GOOGLE_OAUTH_REDIRECT_URI`
- `LILOS_SECRET_ENCRYPTION_KEY`
- `LILOS_GITHUB_APP_ID`
- `LILOS_GITHUB_APP_CLIENT_ID`
- `LILOS_GITHUB_APP_PRIVATE_KEY`

The API and worker must receive the same staging Google application values, Fernet encryption key
and key version, staging authentication values, staging telemetry destination, and staging GitHub
App credentials. `LILOS_WEB_ORIGINS` is the bare HTTPS origin of the staging frontend, without a
path. Generate a new Fernet key for staging; never reuse the production encryption key.

If a provider integration is not part of the approved acceptance run, its placeholders may remain
unconfigured only if Render permits the Blueprint creation and the associated scenarios are marked
blocked. Do not substitute production credentials.

## Callback registration

After Render assigns the API hostname, register these exact staging callback paths against the
staging-only provider applications:

- Google OAuth:
  `https://<lilos-staging-api-host>/api/v1/integrations/google/callback`
- GitHub App setup callback:
  `https://<lilos-staging-api-host>/api/v1/integrations/github/callback`

Set the identical full URLs in `LILOS_GOOGLE_OAUTH_REDIRECT_URI` and
`LILOS_GITHUB_APP_INSTALLATION_REDIRECT_URI`, respectively. Register the staging frontend's HTTPS
origin/redirect patterns in the isolated authentication project and set that bare origin as
`LILOS_WEB_ORIGINS`. No production callback or frontend origin is valid in staging.

## Immutable deployment procedure

Record the intended staging commit from the remote worker branch. Deploy the API first so its
predeploy migrates the isolated database, then deploy the worker using the exact same commit:

```sh
git ls-remote origin refs/heads/worker/backend-closure-2026-08-10
render deploys create <STAGING_API_SERVICE_ID> --commit <STAGING_COMMIT_SHA> --wait
render deploys create <STAGING_WORKER_SERVICE_ID> --commit <STAGING_COMMIT_SHA> --wait
render deploys list <STAGING_API_SERVICE_ID> --output json
render deploys list <STAGING_WORKER_SERVICE_ID> --output json
```

Do not start Packet 2 until both successful deploy records show the identical commit. Never use the
production service IDs in these commands.

## Verification

```sh
curl --fail --silent --show-error \
  https://<lilos-staging-api-host>/health/live
curl --fail --silent --show-error \
  https://<lilos-staging-api-host>/health/ready
render jobs create <STAGING_API_SERVICE_ID> \
  --start-command "alembic current --check-heads"
render jobs create <STAGING_API_SERVICE_ID> \
  --start-command "HEARTBEAT_SERVICES=lilos-worker HEARTBEAT_ENVIRONMENT=staging HEARTBEAT_EXPECTED_RELEASE=<STAGING_COMMIT_SHA> python -m scripts.verify_runtime_heartbeats"
render logs --resources <STAGING_API_SERVICE_ID>,<STAGING_WORKER_SERVICE_ID> \
  --level error --output json
```

Readiness must report PostgreSQL healthy. The Alembic job must report the repository's single head.
The heartbeat job must report one fresh `lilos-worker` heartbeat with the expected release. Logs
and telemetry must route only to the staging destination and must not expose environment values.

## Provider-write window

Read-only discovery and synchronization can run while `LILOS_PROVIDER_WRITES_ENABLED=false`.
Publishing acceptance requires all of the following before an administrator temporarily changes
the `lilos-staging-runtime` value to `true`:

1. written approval for the named provider scenario and time window;
2. staging-only Google/GitHub applications, accounts, locations, and repositories;
3. confirmed provider-resource mappings to those non-production resources;
4. resource-level write enablement and normal LILOs approval/entitlement controls; and
5. active staging telemetry and an identified rollback/reconciliation owner.

Restore `LILOS_PROVIDER_WRITES_ENABLED=false` immediately after the approved scenarios and confirm
the worker has restarted with the safe value. A Blueprint sync also restores the committed safe
default. The kill switch supplements, and never replaces, tenant scope, approvals, entitlements,
resource mapping, idempotency, audit, or provider-side permissions.

## Teardown and cost

Render bills the two Starter services and Basic PostgreSQL while provisioned. PostgreSQL disk size
cannot be reduced. After acceptance evidence and the approved retention window are complete,
deprovision the `lilos-platform-staging` Blueprint resources through Render rather than deleting
individual rows or manually altering the database. Export only approved non-secret acceptance
evidence. Deletion is destructive; confirm the exact staging resource IDs and required retention
before removal. If retained as ongoing staging, assign cost, patching, credential rotation, backup,
telemetry, and access-review owners.
