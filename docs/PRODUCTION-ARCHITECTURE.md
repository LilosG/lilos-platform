# Production Architecture

The production release is four independently deployable processes: Astro frontend, FastAPI API, durable worker, and scheduler. PostgreSQL 17 is the system of record. Authentication remains Supabase JWT verification; secrets remain behind injected references; provider actions use integration adapters and durable job/outbound-action boundaries. Telemetry exports through the provider-neutral endpoint configured at runtime.

Traffic may reach the API only after readiness confirms database access and startup configuration. Worker and scheduler readiness is established by heartbeats. Network policy must expose only frontend/API ingress; database, secret storage, telemetry, worker, and scheduler endpoints remain private. Every artifact is tied to an immutable release and migrations run as a distinct least-privilege deployment step.

No infrastructure vendor is selected in source. The authoritative vendor-neutral process and gate contract is `infrastructure/production/release-contract.yaml`. Actual topology, regions, scaling, and geographic recovery require approved production accounts and architecture review.
