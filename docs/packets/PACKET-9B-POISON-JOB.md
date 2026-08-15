# Packet 9B — Poison Job and Diagnostic Fields

**Branch:** `packet/9b-poison-job` off `main`
**Builder:** DeepSeek V4 Pro
**Depends on:** Packet 9A (merged, `84ec7f6`)

Packet 9A stopped the process from dying. The job still cannot complete, and the diagnostic fields 9A added never reach the logs. This packet closes both.

---

## Evidence

After 9A deployed, a live crawl was triggered. The worker survived — no restarts — and logged every 10 seconds:

```
event_name: process.database.deterministic_error
normalized_error_code: DATABASE_DETERMINISTIC_ERROR
exception_type: IntegrityError
operation: poll
```

Database state:

```
jobs
e5062557… workflow.execute claimed attempt_count=3 max_attempts=3

job_attempts
e5062557… attempt_number=1 status=running safe_error=NULL
e5062557… attempt_number=2 status=running safe_error=NULL
e5062557… attempt_number=3 status=running safe_error=NULL

workflow_runs
87775e8e… status=queued failure_code=NULL
```

Three facts follow:

1. `operation: poll` with the workflow run still `queued` and `failure_code` NULL means the failure occurs in `claim()`, before any handler executes. The crawl handler is not the failing code.
2. Every attempt is `running` with no `safe_error`. No attempt is ever closed, so the lease expires and the job is reclaimed indefinitely.
3. `constraint_name`, `table_name`, and `safe_detail` are absent from the log line despite 9A setting them.

---

## 1. The log formatter drops the diagnostic fields

`apps/api/app/logging_config.py` builds each record from a hardcoded allowlist of field names. `constraint_name`, `table_name`, `schema_name`, `sqlstate`, and `safe_detail` are not in it, so `JsonFormatter` discards them.

Fix so structured diagnostic fields survive. Preferred: pass through any non-reserved key present on the record rather than maintaining an allowlist that silently loses new fields, keeping `redact()` applied to the whole payload. If an allowlist is retained for a stated reason, add the five fields above and explain why the allowlist stays.

Add a test asserting a record carrying `constraint_name` and `safe_detail` emits both.

## 2. Identify the failing write

With section 1 fixed, redeploy and trigger a crawl. The log will name the constraint and table. Report both plainly.

Do not guess. If the fields still do not appear, say so and stop.

## 3. Jobs at max_attempts must not be reclaimable

`claim()` in `apps/api/app/execution/service.py` re-claims a job when `status == "claimed"` and `lease_expires_at < now`. There is no `attempt_count < max_attempts` condition, so a job that fails before recording an outcome cycles forever.

Add that condition. A job at or past `max_attempts` must move to a terminal state — `dead_lettered` — rather than being reclaimed.

## 4. Reclaim must close the abandoned attempt

When a job is reclaimed after lease expiry, the previous `job_attempts` row stays `running` forever. Close it: set a terminal status, a completion timestamp, and a safe error indicating lease expiry, before opening the new attempt.

Report whether existing `finish()` semantics already cover part of this.

## 5. Sweep abandoned leases

A job whose lease expired with no live owner should be reconciled by the runtime, not left for an operator. Add a bounded sweep that closes abandoned attempts and either requeues within `max_attempts` or dead-letters beyond it.

State where this runs and how often.

## 6. Reconcile current orphaned state

One job with three open attempts, and `seo_crawl_runs` rows sitting `queued` with `started_at` NULL and no live job.

Provide a migration or documented operator procedure that brings these to a truthful terminal state. Manual SQL was required twice today; that must stop being the remedy.

---

## Acceptance

1. A log record carrying `constraint_name` and `safe_detail` emits both. Test included.
2. The failing constraint and table are named from a real production log line, or the report states plainly that they still did not appear.
3. A job at `max_attempts` cannot be claimed. Test.
4. Reclaim closes the prior attempt with a terminal status and safe error. Test.
5. Abandoned leases are swept without operator intervention. Test.
6. Current orphaned rows reconcile through a supported path.
7. Full gate: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`, `uv run pytest`, `git diff --check`. Database-backed tests must run.

Do not commit, merge, or push.
