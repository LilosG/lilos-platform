# Packet 9A — Worker Crash Loop

**Branch:** `packet/9a-worker-crash-loop` off `main`
**Builder:** DeepSeek V4 Pro
**Priority:** Blocks Packet 9. The worker crash-looped in production for 30 minutes and only stopped after manual database intervention.

---

## What happened

Owner triggered the first live SEO crawl of wheylandelectric.com through the deployed platform. The worker:

1. Claimed the crawl job
2. Raised `IntegrityError` during execution
3. The runtime classified it as `DATABASE_UNAVAILABLE` and retried
4. Failed identically twice more, hit `database_failure_limit`, re-raised
5. Process terminated; Render restarted it
6. The job's lease had expired, so it was reclaimable — back to step 1

This repeated every ~30 seconds until the queued jobs were manually set to `dead_lettered`. It could not self-recover.

**Database evidence at the time of the loop:**

```
jobs:
8ddaf50b… claimed attempt_count=2 max_attempts=3
804c31c4… claimed attempt_count=3 max_attempts=3

job_attempts: every row status='running', none completed
seo_crawl_runs: two runs status='queued', started_at NULL
```

Attempts were opened and never closed, which is consistent with the process dying mid-execution rather than the handler failing cleanly.

**Prior crawl runs record `{"pages_crawled": 1}`** — the pre-Packet-4A crawler. No live crawl has ever completed with the new engine.

---

## 1. Find the actual constraint violation

The runtime logs only `exception_type: IntegrityError` and discards the Postgres detail, which is why diagnosis required manual SQL. Find the write that violates.

Primary suspect — `execute_crawl` in `apps/api/app/products/seo/service.py`. Opportunity creation does check-then-insert:

```
existing_opportunity = await session.scalar(select(SEOOpportunity).where(... deduplication_key ... active_marker == "active"))
if existing_opportunity: continue
... session.add(opportunity)
```

The crawl engine runs with `concurrency=2`, and `persist_page` is the per-page callback that creates opportunities. Two concurrent callbacks can both pass the existence check and both insert, violating:

```
uq_seo_active_opportunity UNIQUE (organization_id, deduplication_key, active_marker)
```

This is the same race that was fixed for `seo_pages` with an upsert in Packet 4A-R, and left unfixed for opportunities.

**Verify this is actually the failing write before changing it.** Reproduce against a real database with concurrency > 1 and a page set that yields duplicate deduplication keys. If the real cause is elsewhere, fix that instead and report the correction.

## 2. Fix the constraint violation

Replace check-then-insert with a Postgres upsert targeting `uq_seo_active_opportunity`, consistent with how `persist_page` handles `uq_seo_page_normalized_url`. Preserve current semantics: an existing active opportunity for the same deduplication key is not duplicated and not overwritten with a fresh evidence snapshot unless that is the existing behavior.

Audit every other insert reachable from a workflow handler for the same check-then-insert pattern under concurrency, and report what you find.

## 3. `IntegrityError` must not be classified as `DATABASE_UNAVAILABLE`

`run_process` in `apps/api/app/execution/runtime.py` catches `SQLAlchemyError` broadly and treats every case as a transient database failure worth retrying against `database_failure_limit`.

A constraint violation is deterministic. Retrying it produces the identical failure, exhausts the limit, and kills the process. That is what turned one bad write into a 30-minute outage.

Separate the cases:

- **Transient** — connection loss, timeout, operational error: retry as today.
- **Deterministic** — `IntegrityError`, `DataError`, `ProgrammingError`: do not retry the process loop. Fail the individual job through the normal outcome path with a safe error, and keep the worker alive.

The worker must survive a bad job. A single poisonous job must never take down job processing for the whole platform.

## 4. Log the Postgres detail

`IntegrityError` carries `.orig` with the constraint name, table, and detail. That is currently discarded, leaving only `exception_type`.

Log the constraint name and a safe, redacted detail on database failures. No secrets, no full row contents. The next occurrence must be diagnosable from logs alone.

## 5. Poison-job protection

Both crash-looping jobs were reclaimable because their lease expired while `attempt_count` was already at or near `max_attempts`.

- A job at `attempt_count >= max_attempts` must not be reclaimable regardless of lease state.
- An expired-lease reclaim must close the abandoned `job_attempts` row rather than leaving it `running` forever.
- Report whether a job can currently cycle indefinitely, and close that path if so.

## 6. Clean up the orphaned state

Two `seo_crawl_runs` rows sit `queued` with `started_at` NULL and no live job, and several `job_attempts` rows are permanently `running`.

Provide a migration or documented operator procedure — not manual SQL — that reconciles these to a truthful terminal state. Manual SQL was required to stop this incident; that must not be the standard remedy.

---

## Acceptance

1. The failing write is identified with evidence, not inference. Name the constraint and the code path.
2. Fixed such that concurrent execution cannot violate it. Test with concurrency > 1 against a real database.
3. `IntegrityError` fails the job, not the process. Test: a handler raising `IntegrityError` leaves the worker running and the job in a terminal state.
4. Constraint name and safe detail appear in logs on database failure. Show the log line.
5. A job cannot be reclaimed past `max_attempts`. Test.
6. Orphaned crawl runs and attempts reconcile through a supported path.
7. Full gate: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`, `uv run pytest`, `git diff --check`. Database-backed tests must run — CI has `LILOS_TEST_DATABASE_URL` configured and currently passes 795 tests with zero skips.

Report the root cause as a fact traceable to source, not a hypothesis.

Do not commit, merge, or push.
