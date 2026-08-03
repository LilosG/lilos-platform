# Production Architecture

The approved production runtime keeps the Astro frontend on Vercel, uses Supabase Oregon for PostgreSQL 17 and Auth, and runs the FastAPI API, durable worker, and scheduler as three independent Render Oregon services. Provider actions continue to use the shared integration adapters and durable job/outbound-action boundaries. Telemetry exports through the provider-neutral endpoint configured at runtime.

Render builds one portable backend image from the repository root with `infrastructure/docker/backend.Dockerfile`. `lilos-api` binds `0.0.0.0:$PORT`; Render gates it on `/health/ready` while `/health/live` remains process-only. `lilos-worker` and `lilos-scheduler` are background workers with no public ingress. Render sends `SIGTERM`; the API receives 30 seconds, the scheduler 60 seconds, and the durable worker Render's maximum 300 seconds before forced termination. No persistent application disk is used.

The worker and scheduler are continuous asyncio processes over the shared PostgreSQL execution
tables. Both validate production configuration, prove database connectivity, upsert a bounded
15-second service heartbeat, and use interruptible 1-to-10-second idle backoff. The worker claims
with `FOR UPDATE SKIP LOCKED`, renews its 60-second lease during execution, commits result and retry
state atomically, and stops claiming after SIGTERM/SIGINT. Its execution cycle is capped at 270
seconds so an unfinished claim remains recoverable before Render's 300-second limit. The scheduler
atomically locks one due schedule, derives its next timezone-aware occurrence, creates the
idempotent workflow/job intent, and advances the schedule in the same transaction; its cycle cap is
45 seconds inside Render's 60-second limit. Consecutive database failures terminate either process
after three bounded attempts so orchestration can restart it. Neither process uses Redis, Render
queues, Cron, Workflows, or placeholder keepalive loops.

The root `render.yaml` is the Render-specific projection of the portable contract in `infrastructure/production/release-contract.yaml`. It creates no Render Postgres, Key Value, Workflow, cron, or persistent disk. Supabase connections remain injected secrets, OpenTelemetry remains provider-neutral, and Vercel remains outside the Render Blueprint. Production accounts, values, domains, scaling approval, and geographic recovery evidence remain external prerequisites.
