# PR45 — Scheduler Hour-Boundary Determinism

## Scope

Fix the unrelated integrated-test failure exposed while validating PR44:

`tests/python/workflows/test_scheduled_execution.py::test_scheduled_execution_end_to_end[asyncio]`

The failure was:

- first `scheduler.cycle()` returned `True` as expected;
- second `scheduler.cycle()` also returned `True`;
- the test expected `False` with the assertion that no schedule was due again.

This packet is a test-determinism correction unless investigation proves a production scheduler defect.

## Root-cause hypothesis to verify

The test currently sets:

```python
due_at = datetime.now(UTC) - timedelta(minutes=1)
cron_expression = "0 * * * *"
```

`ExecutionService.dispatch_due_schedule()` advances the schedule by asking `croniter` for the next occurrence after `scheduled_for`, not after wall-clock `now`.

Near an hour boundary, this is valid catch-up behavior. Example:

- test begins at `10:00:20`;
- `due_at` becomes `09:59:20`;
- first dispatch advances `next_run_at` to `10:00:00`;
- `10:00:00` is still due at the second scheduler cycle;
- the second cycle correctly dispatches another catch-up occurrence.

Therefore the existing test's statement `no schedule is due again` is not guaranteed by its own setup.

## Required implementation

1. Inspect `ExecutionService.dispatch_due_schedule()` and scheduler runtime semantics before editing.
2. Preserve production catch-up semantics unless concrete evidence shows they are wrong.
3. Make the end-to-end duplicate-dispatch test deterministic by selecting a due scheduled instant whose next hourly cron occurrence is guaranteed to be in the future relative to the test's wall-clock time.
4. Preferred setup for the hourly schedule is the current UTC hour boundary, e.g. derive one `now` value and set:

```python
now = datetime.now(UTC)
due_at = now.replace(minute=0, second=0, microsecond=0)
```

This produces one due hourly occurrence and guarantees the next occurrence is the following hour.
5. Do not weaken the assertions proving:
   - first cycle dispatches;
   - schedule advances;
   - second cycle does not duplicate that occurrence;
   - exactly one run exists for the test schedule;
   - worker/handler/history/tenant-isolation checks remain intact.
6. Add or adjust a focused regression only if useful to explicitly document catch-up semantics around an hour boundary. Do not change product scheduler behavior just to satisfy the old assertion.
7. Do not modify GBP/Integrations/PR44 code.

## Validation

Run focused workflow/scheduler tests first. If green, run the repository-required integrated validation once.

Do not rerun unchanged failures. If investigation reveals a real scheduler product defect instead of a test-time boundary defect, stop and report the evidence before broadening scope.

## Git

Commit and push only this scheduler-test determinism packet to:

`fix/scheduler-hour-boundary-test-2026-08-24`

Do not merge.
