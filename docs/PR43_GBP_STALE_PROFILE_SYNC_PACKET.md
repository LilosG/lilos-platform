# PR43 — GBP Stale Profile Sync Packet

## Scope

Fix one production defect only: Google discovery succeeds for Wheyland Electric but the confirmed mapped GBP resource remains stale because `GBPDiscoveryService.discover_and_sync()` only calls `sync_profile()` when `last_synced_at is None`.

Production evidence on 2026-08-23:

- Google connection is connected.
- Business Profile, Search Console, and Analytics scopes are granted.
- Discovery succeeds with 2 account(s) and 17 location(s).
- Wheyland Electric mapping remains confirmed but stale.
- The Integrations read model marks profile sync older than 24 hours as stale.
- The current discovery flow skips any location that has a non-null historical `last_synced_at`, even if that timestamp is older than the freshness threshold.

## Required correction

1. Use one canonical GBP profile-sync freshness threshold for both:
   - `GBPDiscoveryService.discover_and_sync()` refresh eligibility.
   - `IntegrationDirectoryService._confirmed_mappings()` freshness reporting.
2. Current product behavior is 24 hours. Preserve that value unless repository authority proves otherwise.
3. `discover_and_sync()` must sync a location when:
   - it has never been synced; or
   - its last successful profile sync is older than the canonical freshness threshold.
4. It must skip provider profile reads for locations that are still fresh.
5. Preserve individual-location failure isolation: one profile read failure must not block discovery or synchronization of other eligible locations.
6. Preserve tenant scope, existing confirmed mappings, OAuth state, write permissions, audit events, and provider resource identities.
7. Do not alter GBP provider-write enablement, post publishing, Reviews, Hermes, SEO, Content, onboarding, or unrelated Integrations behavior in this packet.
8. Do not make stale state appear fresh without actually obtaining a new successful provider profile snapshot.

## Expected implementation shape

Prefer a small canonical helper/constant in the GBP domain rather than duplicating `timedelta(hours=24)` in Integrations and discovery.

A reasonable contract is equivalent to:

- `PROFILE_SYNC_FRESHNESS = timedelta(hours=24)`
- `profile_sync_is_stale(last_synced_at, now=...)`

The helper must treat `None` as needing sync and must compare timezone-aware UTC datetimes safely.

Use the existing `sync_profile()` path. Do not create a parallel sync mechanism.

## Focused regression coverage

Add focused tests proving all of the following:

1. never-synced discovered location -> profile sync executes.
2. stale previously-synced location (>24h) -> profile sync executes and `last_synced_at` advances.
3. fresh previously-synced location (<24h) -> provider profile read is skipped.
4. one stale location failing profile read does not block another eligible location.
5. Integrations freshness uses the same canonical threshold as discovery eligibility.

Do not weaken existing tests.

## Verification discipline — no test loops

Follow `AGENTS.md`.

During implementation run only the narrow relevant checks first:

- formatter/lint/type checks needed for touched Python files;
- focused GBP discovery/directory regression tests.

Once focused checks are green, run the repository-required integrated/release validation **once** for packet acceptance. Do not repeatedly run the full suite after every edit. If an unrelated full-suite failure occurs, stop and report the exact failing gate rather than entering a retry loop.

## Git constraints

Target branch: `fix/gbp-stale-profile-sync-2026-08-23`

- Do not reset, clean, rebase, or force-push.
- Do not touch unrelated local work.
- Commit only this packet.
- Push only this branch.
- Do not merge.

## Acceptance state

This packet may become `IMPLEMENTED_NOT_ACCEPTED` after CI is green.

It becomes live-read accepted only after production deployment and a single controlled Google discovery/sync proves Wheyland Electric changes from stale to fresh with a current successful profile sync timestamp.
