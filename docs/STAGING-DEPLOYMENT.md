# Governed Render Staging Deployment

`render.staging.yaml` is the smallest permanent non-production runtime projection available for
Packet 2 acceptance. It reuses the production Docker image and start/predeploy scripts, but creates
an independent protected Render environment containing only:

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
- No production database URL, provider application, encryption key, telemetry endpoint, provider
  token, service-role credential, or application secret may be reused.
- For a short-lived acceptance deployment, the API may verify JWTs from the existing Supabase Auth
  issuer and public JWKS endpoint. This is verification-only reuse: the staging backend receives no
  Supabase administrative credential, performs no Auth management operation, and maps the verified
  subject only to rows in the isolated staging PostgreSQL database. The acceptance run must reuse
  an already-verified MFA factor and must not enroll or remove a production factor.

## Confirmed external inventory

Read-only inventory on 2026-08-10 confirmed that this Render workspace has no staging or preview
application resources, no projects/environments, and no staging environment group or Blueprint.
The only LILOs resources are the production `lilos-api`, `lilos-worker`, and `lilos-scheduler`, the
`lilos-production` Blueprint, and `lilos-production-runtime` environment group. The workspace also
contains an unrelated free PostgreSQL 16 database named `service-ops-starter-db`; it is not a LILOs
resource and must not be reused. The workspace's single free Postgres allowance is therefore
already consumed.

## One-time Blueprint provisioning

In the Render Dashboard, select **New > Blueprint** and use exactly:

- Blueprint name: `lilos-platform-staging`
- repository: the LILOs platform repository
- linked branch: `worker/backend-closure-2026-08-10`
- Blueprint Path: `render.staging.yaml`

Review the plan before applying it. It must contain one project/environment, one PostgreSQL
database, and the two services listed above. It must not update `lilos-api`, `lilos-worker`,
`lilos-scheduler`, or any production datastore or environment group.

Before applying, open **Workspace Settings > Billing** and confirm the workspace is on Render Pro
or higher. Render requires Pro for cross-environment private-network isolation. If the workspace is
Hobby, obtain cost approval and upgrade it; do not remove `networking.isolation` as a shortcut.

The Blueprint has no `sync: false` placeholders, so provisioning requires zero manual Render values.
Render automatically:

- supplies `LILOS_DATABASE_URL` to API and worker from the private staging database;
- supplies `LILOS_MIGRATION_DATABASE_URL` to API from that same isolated database;
- generates one 256-bit `LILOS_SECRET_ENCRYPTION_KEY` in the staging-scoped environment group and
  shares it with API and worker; and
- supplies all non-secret runtime constants, including `LILOS_PROVIDER_WRITES_ENABLED=false`.

The generated Fernet key is staging-only and must never be copied to another environment.

## Minimum initial configuration

The API and worker both boot, migrations run, and health/heartbeat checks work without provider or
telemetry values. To authenticate the existing acceptance identity from the Vercel preview,
bulk-add exactly these three API-only values after the Blueprint creates `lilos-staging-api`:

```dotenv
LILOS_SUPABASE_AUTH_ISSUER=<EXISTING_AUTH_ISSUER>
LILOS_SUPABASE_AUTH_JWKS_URL=<EXISTING_AUTH_JWKS_URL>
LILOS_WEB_ORIGINS=<VERCEL_PREVIEW_HTTPS_ORIGIN>
```

In the Dashboard open **lilos-staging-api > Environment > Add from .env**, paste the three lines,
then choose **Save only**. Do not add them to the worker: it does not verify browser tokens or serve
CORS requests. Deploy API and worker together afterward using the immutable procedure below.

The issuer and JWKS URL are public verifier configuration, not Supabase service-role or management
credentials. The API's Supabase integration only fetches JWKS and verifies issuer, audience,
signature, expiry, subject, session, role, anonymity, and assurance claims. It has no Supabase
client or credential capable of creating, changing, or deleting an Auth user. The verified
`auth.users.id` must still be mapped into the isolated application database.

Bootstrap that first staging identity through the existing idempotent domain-service script, not
SQL or an unsafe HTTP route:

```sh
render jobs create <STAGING_API_SERVICE_ID> \
  --start-command "PILOT_OWNER_AUTH_USER_ID=<EXISTING_AUTH_USER_UUID> PILOT_ORGANIZATION_NAME='Wheyland Electric' PILOT_ORGANIZATION_SLUG=wheyland-electric PILOT_INDUSTRY_KEY=home_services python -m scripts.provision_pilot_owner"
```

Only the existing Auth user UUID varies; the Wheyland name, slug, and seeded industry key are fixed
non-secret job constants. The script creates the platform user, active organization, membership,
and owner assignment transactionally and idempotently.

The existing Vercel preview already uses the matching Supabase URL and public anon key. Retain
those values. Add only this branch-specific Preview override for
`design/platform-professional-ux-v1-2026-08-08`:

- `PUBLIC_LILOS_API_BASE_URL=<LILOS_STAGING_API_ORIGIN>`

Do not add branch-specific Supabase overrides. Password sign-in, session refresh, and challenge of
the acceptance user's already-verified TOTP factor may continue through the existing public Auth
client. Do not enroll or unenroll a factor during staging acceptance.

## Wheyland acceptance-state boundary

The repository has no governed command that clones or imports an organization's application state.
That is intentional: migrations create schema, catalog seeds create only global platform catalogs,
and provider discovery recreates current provider observations rather than prior LILOs decisions or
histories. `scripts/provision_pilot_owner.py` creates only the user mapping, active organization,
membership, and owner role.

State available without copying production rows is classified as follows:

| State | Classification | Supported path |
| --- | --- | --- |
| Schema, industries, roles, permissions, products, configuration definitions, provider registry | `AUTOMATIC_FROM_MIGRATIONS_OR_SEEDS` | API predeploy |
| Acceptance user mapping, Wheyland organization, active membership, owner role | `GOVERNED_BOOTSTRAP` | `scripts.provision_pilot_owner` |
| Organization/location profiles, primary location/domain, product entitlements, approval policy, approved business facts | `REQUIRES_MANUAL_OPERATOR_SETUP` | Authenticated administration/onboarding APIs; no consolidated script exists |
| Google and GitHub connections/callback registrations | `REQUIRES_MANUAL_OPERATOR_SETUP` | Separate provider applications, credentials, authorization/install |
| GBP accounts/locations/profile snapshots | `RECREATED_BY_PROVIDER_DISCOVERY` | Staging Google OAuth and discovery |
| Confirmed shared provider-resource mappings | `REQUIRES_MANUAL_OPERATOR_SETUP` | Explicitly confirm each discovered provider resource against the staging location |
| Reviews and review revisions | `RECREATED_BY_PROVIDER_DISCOVERY` | Ingest from the confirmed discovered GBP location |
| Search Console and GA4 properties/observations | `RECREATED_BY_PROVIDER_DISCOVERY` | Discover, explicitly map, then sync |
| SEO website/current crawl/pages/opportunities | `GOVERNED_BOOTSTRAP` | Create the website and execute a new bounded crawl through normal APIs |
| Content items/briefs/revisions | `SAFE_MINIMAL_TEST_FIXTURE` | Create synthetic acceptance records through normal APIs; never label them imported production history |
| GitHub repositories | `RECREATED_BY_PROVIDER_DISCOVERY` | Staging GitHub App installation and repository discovery |
| GitHub publishing target | `REQUIRES_MANUAL_OPERATOR_SETUP` | Explicitly choose the discovered staging repository, branch, and allowed path |
| Insights current summary | `RECREATED_BY_PROVIDER_DISCOVERY` | Derived from newly created workflows, GBP, Reviews, SEO, Leads, Content, and GA4 rows |
| Workflow definitions/versions/runs and audit events | `GOVERNED_BOOTSTRAP` | Created lazily by normal workflow/domain actions and their audit services |
| Existing Wheyland approvals, publications, lead source/history, content history, workflow outcomes, and audit chronology | `CANNOT_BE_REPRESENTATIVELY_STAGED` | Not provider-owned and no governed export/import exists; copying production rows is prohibited |

There is also no production-mounted API or repository provisioning script that creates the
`LeadSource` required before lead intake. Python test fixtures insert a synthetic source directly
with the ORM, but they are test-only, have no staging guard, and are not an approved live bootstrap
mechanism. Do not execute test fixtures against staging.

Consequently, this environment is sufficient for deployment, migration, authentication, tenant
isolation, empty-state, provider-discovery, new-workflow, and provider-write-kill-switch acceptance.
It cannot by itself reproduce the consolidated existing Wheyland history. A staging run must be
described as newly reconstructed acceptance state, never as a clone of the production client.

Reconstructing the minimum readiness foundation after the pilot-owner job currently requires 18
governed application mutations: organization profile (1), primary location creation and activation
(2), location profile (1), primary domain (1), seven product entitlements including Automations
(7), business-fact reconciliation (1), approval of the three derivable facts (3), and proposal plus
approval of business hours (2). Provider discovery, property mapping/sync, SEO crawl, Content
workflow creation, and GitHub setup are additional actions. Leads cannot reach a representative
non-empty state through a supported staging operation because no governed Lead Source creation path
exists.

If the release objective is consolidated acceptance against the already-populated Wheyland history,
staging is not a substitute for a controlled production deployment. Provision staging only as a
deployment/migration/authentication/worker smoke gate, or after a separately reviewed staging-data
bootstrap capability exists. Never expand this runbook into row copying or manual SQL.

## Deferred configuration

Do not configure these for the first API/auth/read-only acceptance pass:

- Google: `LILOS_GOOGLE_OAUTH_CLIENT_ID`, `LILOS_GOOGLE_OAUTH_CLIENT_SECRET`, and
  `LILOS_GOOGLE_OAUTH_REDIRECT_URI`;
- GitHub: `LILOS_GITHUB_APP_ID`, `LILOS_GITHUB_APP_CLIENT_ID`,
  `LILOS_GITHUB_APP_PRIVATE_KEY`, and `LILOS_GITHUB_APP_INSTALLATION_REDIRECT_URI`; and
- optional staging telemetry: `LILOS_TELEMETRY_EXPORT_ENDPOINT`.

When an integration phase is approved, open **Environment Groups > lilos-staging-runtime > Add
from .env** and add the Google/GitHub values once. That staging-scoped group is already linked to
both services, so the worker receives the same provider and encryption configuration without
duplicate entry. Add only API-specific values directly to the API. Keep provider writes disabled.

## Deferred callback registration

Only when the corresponding provider phase is approved, register these exact staging callback
paths against staging-only provider applications:

- Google OAuth:
  `https://<lilos-staging-api-host>/api/v1/integrations/google/callback`
- GitHub App setup callback:
  `https://<lilos-staging-api-host>/api/v1/integrations/github/callback`

Set the identical full URLs in `LILOS_GOOGLE_OAUTH_REDIRECT_URI` and
`LILOS_GITHUB_APP_INSTALLATION_REDIRECT_URI`, respectively. Set the staging frontend's bare HTTPS
origin as `LILOS_WEB_ORIGINS`. No production provider callback or production frontend origin is
valid in staging.

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

Do not start staging Packet 2 scenarios until both successful deploy records show the identical
commit. Never use the production service IDs in these commands. Do not claim consolidated Wheyland
history acceptance from this environment.

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
must not expose environment values. If optional telemetry is configured, it must route only to the
staging destination.

## Provider-write window

After the deferred Google configuration is supplied, read-only discovery and synchronization can
run while `LILOS_PROVIDER_WRITES_ENABLED=false`.
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

Render bills the two Starter services and Basic PostgreSQL while provisioned. At current published
price points, two Starter services plus a Basic-256mb database with the Blueprint's 15 GB storage
are approximately **$25/month**, before bandwidth or other usage. If the workspace is currently
Hobby, the Pro workspace plan required for network isolation adds approximately **$25/month**.
PostgreSQL disk size cannot be reduced. After acceptance evidence and the approved retention window
are complete, deprovision the `lilos-platform-staging` Blueprint resources through Render rather
than deleting individual rows or manually altering the database. Export only approved non-secret
acceptance evidence. Deletion is destructive; confirm the exact staging resource IDs and required
retention before removal. If retained as ongoing staging, assign cost, patching, credential
rotation, backup, telemetry, and access-review owners.
