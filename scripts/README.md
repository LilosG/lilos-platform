# Scripts

Repository maintenance scripts live here. Scripts must be deterministic, documented, and must not
contain credentials or make unapproved external changes.

`npm run db:seed:industries` runs the explicit, transactional initial-industry seed against
`LILOS_DATABASE_URL`. It is idempotent for matching records, reports name mismatches, does not
silently change existing policy JSON, and creates industry audit events through the application
service. Apply migrations first and never point it at an unapproved database.

## Render-shell operator scripts

These are run from the Render shell, which has no `uv` and needs the release id:

```sh
LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.<name> <args>
```

| Script                             | What it does                                                                                                                                                                                                                                        |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `seed_publishing_target_contracts` | Records each client's Astro collection contract, verified page map and site-change prefixes on its existing publishing target. Idempotent.                                                                                                          |
| `reevaluate_active_websites`       | Re-runs Search Console sync, crawl and analysis for every website of an ACTIVE organization. One website's failure is logged and skipped; the summary lists skipped steps with their error type.                                                    |
| `suspend_organization`             | Suspends an organization (by `--organization-id` or `--website-domain`) through the audited `OrganizationService.transition`. Dry run unless `--apply`. Reversible with `activate`.                                                                 |
| `ensure_client_schedules`          | Creates or corrects the recurring schedules (reviews every 6 h; GBP, Search Console, GA4 daily; crawl weekly) of every active organization through the schedule service. Skips and reports organizations with no mapping. Dry run unless `--apply`. |
| `recover_stuck_publications`       | Reads the provider truth of stuck GBP posts, site changes and review replies and resumes each through its canonical recovery service. A dry run rolls back; `--apply --actor-id <platform user id>` keeps it.                                       |
| `site_change_dry_run` (local only) | Proves a governed site change against a local clone of a client repo: prints the diff and checks nothing but the approved values changed. Touches no database and opens no pull request.                                                            |

All the Render-shell scripts share `scripts/_cli.py`, so a missing `LILOS_RELEASE` (exit 2), a
Google connection that needs reconnecting (exit 3) or an unreachable database (exit 1) is reported
as a single line instead of a traceback.
