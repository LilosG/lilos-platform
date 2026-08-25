# PR47 Hermes governed agent runtime decision

Date: 2026-08-24

Status: Implemented in repository; live production acceptance required

## Context and confirmed pre-change gaps

Repository inspection found a private, API-key-authenticated Hermes Render service pinned to
`nousresearch/hermes-agent:v2026.8.3`, plus a governed one-shot completion adapter used by existing
GBP, Content, and Reviews generation. It did not use native Hermes runs for product agent work,
persist native run IDs or structured events, expose approval/stop/real-steer controls, register a
sanctioned LILOs toolset, define cross-product skills, or provide scoped native transcript
continuity. The existing LILOs workflow registry, durable worker, scheduler, approval, audit,
provider-write, and reconciliation architecture was already present and remains authoritative.

The exact v2026.8.3 runtime exposed Runs create/status/events/approval/stop but no HTTP run steer.
Its TUI `session.steer` transport owned a different in-process session map from HTTP Runs, so using
it would not safely steer the active API run. This was a release-blocking runtime gap rather than a
capability to defer.

## Decision

Pin the tested Hermes release
`nousresearch/hermes-agent:v2026.8.19@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09`
(OCI revision `fcbd1076a93841fa88855acce810e342a5b78101`, internal runtime `0.20.5`).
Use its authenticated native protocol:

- `POST /v1/runs`
- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/events` (SSE)
- `POST /v1/runs/{run_id}/approval`
- `POST /v1/runs/{run_id}/steer`
- `POST /v1/runs/{run_id}/stop`
- `DELETE /api/sessions/{session_id}` for a deterministic scoped reset
- `GET /health/detailed`, `GET /v1/capabilities`, and `GET /v1/toolsets` for positive probes

The v2026.8.19 HTTP steer handler calls the live same-process active run agent's native `steer`
method. It is genuine run-scoped Hermes steer; it is not a queued LILOs follow-up and does not use
the separate TUI session map.

LILOs creates five catalog workflows (`agent.gbp`, `agent.seo`, `agent.content`, `agent.reviews`,
and `agent.insights`) and executes them through the existing durable `workflow.execute` worker
path. No Hermes jobs API, cron facility, or second orchestrator is used. Every native run is bound
to its owning `WorkflowRun`, `AIExecution`, tenant/location, versioned skill, capability snapshot,
and audit correlation.

## Capability and tool policy

Agent work is available only when Hermes positively advertises all of `run_submission`,
`run_status`, `run_events_sse`, `run_stop`, `run_steer`, `run_approval_response`,
`tool_progress_events`, and `approval_events`, with runtime mode `server_agent`, server-side tool
execution, and `split_runtime=false`. LILOs also requires exactly one enabled Hermes toolset named
`lilos` with the exact sanctioned contract. Missing features, an extra enabled toolset, a tool
mismatch, or unsafe runtime mode fails closed and is rendered unavailable.

The sanctioned plane uses Hermes' supported custom-plugin registry. The plugin receives only an
opaque run-bound session and calls an authenticated private LILOs endpoint. Organization and
location IDs are absent from every model-visible schema. LILOs derives scope from the bound run,
checks the versioned skill allowlist, calls canonical services, bounds results, rejects secret
material, and audits argument shape/hash/size, result hash/size, sources, proposals, outcome, and
latency. Proposal tools accept only evidence references already returned by sanctioned tools in
that same bound run, so model-authored reference strings cannot become provenance. The toolset
contains 20 tools:

- reads: approved business facts, website knowledge, GBP state/posts, GSC, GA4, Reviews, Content,
  cross-product summary, deterministic SEO opportunities, and owning workflow;
- governed work: request the canonical crawl workflow; create SEO recommendation, Content item,
  Content brief/revision, GBP post/change-set, and Review response proposals; submit only a
  proposal created by the same run for LILOs approval.

There is no Google, GitHub, shell, terminal, arbitrary MCP, provider-credential, or provider-write
tool. Deterministic SEO and Review risk classifiers remain authoritative. All client/provider
changes continue through existing LILOs approval, publication, verification, and reconciliation
workflows.

## Session and event policy

Hermes' Runs body `session_id` owns the durable transcript; `X-Hermes-Session-Key` owns long-term
memory scope. LILOs sends the same opaque key for both, derived from one
organization/location/skill namespace. A database partial unique index permits only one queued,
running, approval-waiting, or stopping run per scoped session, keeping the plugin binding
unambiguous while preserving real cross-run Hermes continuity. A known native run ID is reconnected
after an event-stream failure. An ambiguous create without a native ID fails closed, disables the
old tool binding, and rotates the session before later work so a lost response cannot create a
duplicate authorized agent.

Scoped reset deletes the Hermes session when configured, rotates only that namespace, and records
an audit event. Hermes is configured for 30-day session retention/auto-prune as defense in depth;
LILOs separately bounds session and event access to 30 days by default. Approved LILOs facts are
re-read on every run and override memory.

LILOs persists only allowlisted lifecycle, tool outcome, approval, subagent metric, and terminal
result projections. It drops reasoning, message deltas, private subagent tool content, and
secret-bearing output. Event count, text/result size, and retention are bounded. Chain-of-thought
is never persisted.

## Acceptance consequence

Repository tests and a local exact-image capability/toolset probe establish implementation
evidence only. PR47 remains `IMPLEMENTED_NOT_ACCEPTED` until the packet's production sequence proves
private run creation, real evidence-backed tool use, a cross-product result, a governed proposal,
human approval, stop, real HTTP steer, tenant isolation, audit completeness, and deployed
API/worker/Hermes release parity.
