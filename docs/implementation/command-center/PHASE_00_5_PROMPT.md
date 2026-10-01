# Phase 0.5 — Safe Integration Environment

## Preconditions

Start only after:

- Phase 0 is complete and merged
- Phase 0.5 is marked READY, or all blocking owner actions have been satisfied
- current `main` is clean and current
- `MASTER_PLAN.md` and completed Phase 0 artifacts have been read in full

## Objective

Build the safe integration environment required to wire the Command Center without touching real client assets.

This phase implements infrastructure/test foundations only.

Do not begin full `apps/console` product integration except for the minimum runtime bootstrap needed to validate staging.

## Required scope

Implement the Phase 0-approved staging architecture.

### Staging Supabase

Configure a separate staging Supabase project for:

- Auth
- Postgres
- staging issuer/JWKS
- staging redirect URLs

No production users, production tokens, or copied production data.

### Render staging

Bring staging runtime configuration current with merged `main`.

Required services as approved by Phase 0:

- API
- worker
- scheduler
- Hermes

Use staging-only secrets/config.

### Vercel staging

Configure:

- protected PR previews
- stable staging deployment
- `console-staging.lilosgrowth.com`
- staging-only environment variables
- staging Supabase
- staging API
- approved runtime/region
- Preview/Production environment separation

### Provider simulation

Implement canonical fixture adapters through existing provider interfaces.

Production configuration must refuse fixture providers.

Support deterministic:

- healthy GSC
- healthy GA4
- healthy GBP
- reconnect required
- expired auth
- provider 429/rate limit
- provider failure
- partial data
- missing mapping

Do not add environment-condition branches inside product services.

### Recorded provider contract tests

Implement shared provider contract suites.

Real adapters use deterministic recorded responses in CI.

Fixture adapters satisfy the same normalized contract.

### Live read-only provider smoke

Set up the scheduled/read-only smoke path approved in Phase 0 using independently authorized staging credentials against LILOs-owned properties.

No Google/GBP writes.

### Staging data

Seed synthetic organizations through canonical APIs/services.

Do not copy production client data.

### GitHub staging publishing

Configure one dedicated test repository.

GitHub writes in staging must be restricted to that repo.

Google/GBP writes remain disabled.

If the current broad provider-write switch cannot express this safely, implement the provider-specific capability/allowlist model approved in Phase 0.

### LILOs Growth readiness setup

Perform only items explicitly approved by Phase 0.

Keep production canary preparation separate from staging test-repo configuration.

Do not use client repositories as staging targets.

## Required security validation

Prove:

- preview cannot access production API
- preview cannot authenticate against production Supabase
- staging token invalid against production
- production token invalid against staging
- host-only cookies
- redirect host validation
- no production secret in Preview scope
- no fixture provider allowed in production config
- no staging provider write can target a client repo
- no Google/GBP write can occur from staging

## Required checks

Run all relevant:

- format/lint/typecheck
- backend tests
- migration checks
- staging config checks
- provider contract tests
- secrets checks
- environment-isolation tests
- deployment/config validation

Do not claim deployment success without verifying it.

## Required outputs

Create/update:

```text
docs/implementation/command-center/PHASE_00_5_ACCEPTANCE.md
docs/implementation/command-center/DECISION_LOG.md
```

Record:

- actual staging endpoints
- actual environment boundaries
- actual services
- exact provider simulation mechanism
- exact GitHub test target
- exact owner actions still required
- recurring cost actually introduced

## Definition of done

Phase 0.5 is complete only when there is a safe, isolated, authenticated staging system that can:

- run the backend
- run workers/scheduler/Hermes
- authenticate staging users
- show synthetic data
- simulate provider failures
- run read-only live provider smoke
- publish only to a dedicated GitHub test repo
- never mutate real client assets

Do not begin Phase 1.
Open one coherent PR.
Do not merge automatically.
