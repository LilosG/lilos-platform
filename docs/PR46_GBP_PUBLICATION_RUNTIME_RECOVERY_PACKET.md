# PR46 — GBP Publication Runtime Recovery + Truthful State

## Status

IMPLEMENTATION PACKET — production defect reproduced and root-caused on 2026-08-24 during Wheyland Electric live acceptance.

This is a platform-wide correction. Do not special-case Wheyland Electric.

## Production evidence

Live acceptance established the following sequence:

1. Google connection and mapped GBP location were fresh and provider writes were explicitly enabled through the governed AAL2 flow.
2. A real EV-charger Local Post revision was drafted and approved.
3. The Publish action reserved `gbp.publish_post` and enqueued the durable workflow.
4. `lilos-worker` logged `Token resolution failed in workflow handler` on the first attempt.
5. Production environment inspection showed:
   - `LILOS_DATABASE_URL=SET`
   - `LILOS_SECRET_ENCRYPTION_KEY=SET`
   - `LILOS_GOOGLE_OAUTH_CLIENT_ID=MISSING`
   - `LILOS_GOOGLE_OAUTH_CLIENT_SECRET=MISSING`
   - `LILOS_GOOGLE_OAUTH_REDIRECT_URI=MISSING`
6. Those three Google variables were added to `lilos-worker`; all five are now SET.
7. The original workflow had already retried and escalated to `AMBIGUOUS_PROVIDER_RESULT`.
8. The Posts UI continued rendering the approved revision with an enabled Publish button despite an existing publication attempt.
9. Provider reconciliation changed the displayed count from 75 to 76 even though the test post was not visible in the public GBP Posts UI.

Relevant current behavior:

- `render.yaml` declares worker Google vars as `sync: false`, so Blueprint configuration does not guarantee the secret values actually exist on the worker runtime.
- `scripts/render_start_worker.sh` only validates `RENDER_GIT_COMMIT`; worker startup can be green while enabled provider workflows are impossible to execute.
- `_handle_gbp_publish_post()` changes a publication to `reconciliation_required` on token-resolution failures that occur before `create_local_post()` is called.
- A later retry with `provider_post_id is None` then returns `AMBIGUOUS_PROVIDER_RESULT`, even though the original failure may have been provably pre-dispatch.
- The Posts UI renders revision state but not publication state. An approved revision continues to expose Publish even when a publication row exists.
- Provider reconciliation stores Google `state`, but the UI's “currently visible on Google” count is based on `status == present` rather than provider state `LIVE`.

## Objective

Close the complete failure class, not only the observed instance:

- production worker must fail fast when runtime configuration required by enabled provider workflows is missing;
- pre-provider failures must remain safely retryable and must not be converted into ambiguous-write state;
- actual provider-dispatch ambiguity must remain fail-closed and duplicate-safe;
- post publication state must be a first-class read model exposed to the product UI;
- Publish must not remain available once a publication exists in any active/final state that makes a new dispatch unsafe or redundant;
- provider Local Post counts and labels must distinguish `LIVE`, `PROCESSING`, `REJECTED`, and historical/not-seen truth;
- existing stranded production publication must have a governed, auditable recovery path that does not rely on direct DB edits and cannot duplicate a Google post;
- changes must be tenant-safe and apply to every organization/location.

## Non-negotiable safety rules

1. Never create a second Google Local Post merely because the first workflow is uncertain.
2. Never treat a provider call as having occurred before the durable `dispatched` transition.
3. Pre-dispatch failures (configuration, secret resolution, OAuth token resolution) must not enter ambiguous provider-write state.
4. Provider I/O must remain outside long-held DB transactions.
5. Existing approval, AAL2, tenant/location scope, write-enabled gate, idempotency, audit, provider verification, and reconciliation rules remain intact.
6. Do not invent a second orchestration path. Continue using the existing durable workflow system and canonical GBP services.
7. Do not special-case production IDs, Wheyland, or current timestamps/content.
8. No direct production DB mutation is part of this PR acceptance.

## Required implementation

### A. Worker production runtime preflight

Create a reusable runtime validation path used by `lilos-worker` startup before it reports healthy/running.

When `LILOS_PROVIDER_WRITES_ENABLED=true`, the worker must require the configuration necessary to execute Google provider workflows:

- `LILOS_DATABASE_URL`
- `LILOS_SECRET_ENCRYPTION_KEY`
- `LILOS_GOOGLE_OAUTH_CLIENT_ID`
- `LILOS_GOOGLE_OAUTH_CLIENT_SECRET`
- `LILOS_GOOGLE_OAUTH_REDIRECT_URI`

Do not log secret values. A missing required variable must fail startup with a bounded non-secret message naming only the missing key(s).

Do not make unrelated optional integrations mandatory. If a cleaner capability-aware preflight already exists, extend it rather than creating a parallel framework.

Add focused tests proving:

- provider writes enabled + one Google runtime field missing => worker startup/preflight fails;
- provider writes enabled + required fields present => passes;
- provider writes disabled => Google write configuration is not required solely for worker startup;
- no secret values appear in error/log output.

### B. Correct pre-dispatch vs post-dispatch semantics in `gbp.publish_post`

Refactor `_handle_gbp_publish_post()` so state transitions encode provider-write reality.

Required contract:

1. Validate publication/revision/mapping/write gate and resolve OAuth/token BEFORE marking the publication dispatched.
2. If configuration/secret/token resolution fails before `create_local_post()`:
   - do not mark the publication `dispatched`;
   - do not move it to ambiguous `reconciliation_required` solely because of that pre-dispatch failure;
   - return an appropriate retryable/permanent safe error using the existing execution semantics;
   - a retry after the environment is corrected must be able to resume safely without a duplicate risk.
3. Immediately before the provider create call, persist the durable dispatch boundary.
4. Once the durable dispatch boundary has been crossed, missing provider identity on an interrupted/failed result remains ambiguous and fail-closed.
5. If a `provider_post_id` exists, retries must only re-read that exact provider resource and never create another.
6. Preserve current `LIVE` => verified, `REJECTED` => failed, other provider states => reconciliation/retry behavior.

Prefer the smallest durable state addition needed to distinguish pre-dispatch from post-dispatch. If schema changes are required (for example `dispatched_at` and/or `safe_error_code` on `GBPPostPublication`), add a migration and ensure old rows are handled conservatively.

### C. Governed recovery for stranded publications

Provide an explicit product/service recovery path for publications that cannot automatically proceed.

It must:

- be organization + location scoped;
- require the same high-assurance authorization appropriate for provider publication/recovery;
- be auditable;
- never silently reset an actually-dispatched publication to create-again;
- first reconcile against known/provider Local Posts where provider identity may already exist;
- only permit a pre-dispatch retry when the system has durable evidence the provider create boundary was never crossed;
- otherwise remain `reconciliation_required` / operator attention rather than guessing.

For legacy rows created before the new dispatch evidence exists, default to conservative handling. If exact automatic proof is impossible, surface a governed operator resolution rather than inferring safety from `provider_post_id is null` alone.

The production acceptance goal after deploy is to recover the currently stranded test publication without clicking the ordinary Publish action again and without direct DB edits.

### D. Publication read model + Posts UI

Expose publication truth with each managed revision (or via a canonical publication endpoint consumed by the Posts surface).

At minimum the UI must distinguish:

- Awaiting approval
- Approved / never submitted
- Reserved / queued
- Dispatched / publishing
- Provider processing / reconciliation required
- Published / verified
- Failed / rejected
- Cancelled / expired if supported

Rules:

- Once an active or completed publication exists for a revision, ordinary Publish must be hidden/disabled as appropriate.
- The UI must not generate a fresh publish idempotency key for repeated clicks on a revision that already has an active publication.
- Success/error/status messaging must survive rerender.
- Show a safe recovery action only where the backend recovery contract says it is valid.
- Do not expose raw provider secrets/errors.

Add regression tests for double-click/re-render behavior and publication state rendering.

### E. Truthful Google Local Posts reconciliation/counts

Current provider snapshots already persist Google `state`. Use it.

Do not label every `status == present` row as “currently visible on Google.”

Define explicit provider-state semantics, at minimum:

- `LIVE` => visible/live
- `PROCESSING` (and other transitional non-live states) => observed by provider but not publicly live
- `REJECTED` => rejected/not live
- `not_seen` => historical/not currently returned

The Posts summary must report truthful counts. A suggested shape is:

- `X live on Google`
- `Y processing`
- `Z observed over time`

Exact wording can follow existing status-language conventions, but “visible” must mean provider state `LIVE` only.

Provider reconciliation must remain idempotent and must not delete history.

### F. Inline confirmation layout defect

Fix the shared responsive confirmation layout exposed during provider-write enablement: confirmation text/actions overlapped at narrower widths. Fix the reusable component/layout rather than adding a Wheyland-specific CSS patch. Add an appropriate browser/DOM regression if practical within current test patterns.

### G. Release ledger

Update `docs/PLATFORM-RELEASE-LEDGER.md` with:

- production root cause;
- worker runtime configuration gap;
- pre-dispatch state-machine defect;
- publication-state/read-model defect;
- provider count truthfulness defect;
- recovery behavior;
- validation evidence;
- status `IMPLEMENTED_NOT_ACCEPTED` until deployed live acceptance proves recovery and a real Google post reaches `LIVE`.

## Likely files to inspect/modify

This list is guidance, not permission to ignore adjacent canonical owners found during inspection:

- `render.yaml`
- `scripts/render_start_worker.sh`
- `apps/api/app/config.py`
- `apps/api/app/execution/runtime.py`
- `apps/api/app/execution/handlers.py`
- `apps/api/app/execution/service.py`
- `apps/api/app/products/gbp/operations_models.py`
- `apps/api/app/products/gbp/operations_service.py`
- `apps/api/app/products/gbp/discovery_service.py`
- `apps/api/app/routes/gbp_operations.py`
- `apps/web/src/lib/gbp-operations.ts`
- Business Profile page Posts renderer/actions
- shared inline confirmation UI/CSS
- relevant Python + web + browser tests
- Alembic migration only if durable publication fields are required
- `docs/PLATFORM-RELEASE-LEDGER.md`

## Validation discipline

Follow the project diagnostic rule:

reproduce -> evidence -> owning service -> root cause -> coherent fix -> focused validation -> one integrated validation.

Do not rerun an unchanged failing command. If the same validation fails twice, stop and diagnose.

Required focused acceptance includes:

1. worker runtime preflight matrix;
2. pre-dispatch OAuth/config failure remains safely retryable;
3. provider create is not called on pre-dispatch failure;
4. retry after corrected config performs exactly one provider create;
5. post-dispatch ambiguous result cannot create a duplicate;
6. known provider ID retries only re-read exact provider resource;
7. provider `PROCESSING` does not count as live;
8. provider `LIVE` counts as live;
9. publication state renders and suppresses duplicate Publish;
10. recovery authorization, tenancy, audit, and unsafe-recovery denial;
11. responsive inline confirmation regression.

Then run the repository's normal integrated release validation exactly once after focused checks are green.

If an integrated failure is unrelated to this packet, stop and report it with evidence; do not modify unrelated product code to make the suite green.

## Completion report required from implementation agent

Return:

1. exact root causes confirmed;
2. architecture/state-machine changes;
3. migrations, if any;
4. files changed;
5. worker preflight behavior;
6. pre-dispatch/post-dispatch retry semantics;
7. stranded-publication recovery contract;
8. Posts UI/publication-state behavior;
9. provider Local Post count semantics;
10. confirmation-layout fix;
11. focused validation totals;
12. integrated validation totals;
13. commit SHA;
14. push status;
15. remaining live acceptance steps.

Do not merge. Push only to `fix/gbp-publication-runtime-recovery-2026-08-24` after required validation passes. Keep ledger status `IMPLEMENTED_NOT_ACCEPTED` until live provider acceptance is complete.