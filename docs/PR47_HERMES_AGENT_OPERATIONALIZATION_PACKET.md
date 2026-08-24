# PR47 — Hermes Agent Operationalization / Cross-Product Closure Packet

## Status

PLANNED — implementation and live production acceptance required. This packet is not complete until Hermes is operating as a real governed agent runtime across the LILOs products listed below, with tool-backed reasoning, lifecycle controls, observable run history, and production acceptance.

## Base

This branch is stacked on PR46 commit `a91e64367810d7d45524b472a3007a6ba9fe1cb5` so publication recovery/runtime corrections remain present while agent operationalization is completed.

## Problem statement

LILOs currently routes production AI generation through the private Hermes service, but the integration primarily uses Hermes through the OpenAI-compatible completion surface. That makes Hermes a real inference runtime, but it does not yet capture the full value of Hermes as an agent runtime: durable runs, tool use, cross-product evidence gathering, skills, event streaming, approvals, stop/steer lifecycle, and inspectable multi-step work.

There must be no future-tense placeholder after this packet. The production platform must use Hermes as the governed agent execution layer wherever agent reasoning materially improves the product.

## Non-negotiable architecture

LILOs remains the control plane and source of authority.

LILOs owns:
- organization/location tenant scope;
- approved business facts and source truth;
- entitlements and permissions;
- durable workflow/idempotency state;
- approval policy;
- audit trail;
- provider credentials;
- all external provider mutations and verification;
- deterministic SEO/risk/compliance detectors.

Hermes owns:
- agent reasoning/execution;
- tool sequencing;
- skills;
- session continuity/memory within policy;
- subagent/delegation behavior where justified;
- run lifecycle and streaming events;
- model execution.

Hermes must never bypass LILOs approval, audit, write gates, tenant scope, or provider-write workflows.

Do not create a second workflow/orchestration framework. Hermes runs must bind to the existing LILOs workflow/execution system.

## Current state to preserve

- Production AI provider resolves to `hermes`.
- Hermes is a private Render service authenticated by API key.
- Production model route is pinned to the governed OpenRouter/DeepSeek route on boot.
- Existing grounded AI paths for GBP posts, Content drafts, and Review drafts remain supported.
- Existing deterministic SEO opportunity detection remains deterministic.
- Existing provider mutation workflows remain the only mutation paths.

## Required completion scope

### 1. Hermes native run lifecycle

Replace agent-grade uses of one-shot completion calls with the Hermes Runs API / supported programmatic lifecycle.

Required capabilities:
- create Hermes run and persist the Hermes run ID against the owning LILOs workflow run / AI execution;
- poll/reconcile run status;
- ingest structured run events/tool events into a bounded LILOs read model;
- stop a live run from LILOs;
- approve/deny Hermes approval requests through LILOs policy;
- steer an active run from LILOs.

Steer must be real, not simulated. Current Hermes HTTP Runs API may not expose run-scoped steer. Inspect the pinned Hermes version and `/v1/capabilities`. If HTTP steer is unavailable, use Hermes' supported TUI-gateway JSON-RPC/WebSocket `session.steer` transport, or upgrade the pinned Hermes release to a tested version/transport that exposes supported steer. Do not ship a fake steer button or queue a second turn and label it steer.

Capability probing must fail closed. LILOs UI must only expose controls actually supported by the deployed Hermes runtime.

### 2. Governed LILOs tool plane for Hermes

Hermes must receive a sanctioned toolset backed by canonical LILOs services. Tools must not directly access the database, raw provider credentials, or arbitrary provider APIs.

Minimum tool capabilities:
- `read_client_business_facts`
- `read_website_knowledge`
- `read_gbp_state`
- `read_gbp_recent_posts`
- `read_gsc_evidence`
- `read_ga4_evidence`
- `read_reviews_state`
- `read_content_inventory`
- `run_site_crawl` or request/inspect the canonical crawl workflow
- `analyze_seo_opportunities`
- `create_content_proposal`
- `create_content_brief`
- `generate_gbp_post_proposal`
- `draft_review_response_proposal`
- `inspect_workflow`
- `submit_for_approval`

Tool naming may change to fit existing conventions, but these capabilities must exist.

Tool contract requirements:
- tenant and location scope derive from the bound LILOs agent/workflow run, not model-supplied organization IDs;
- Hermes service authentication is required;
- model-visible arguments cannot grant broader tenant scope;
- every mutating LILOs tool is proposal/workflow creation only, never direct provider mutation;
- all tool calls are audited with tool name, run/workflow identity, safe arguments/result metadata, latency, and outcome;
- secrets and raw credentials never enter Hermes prompts/tool output;
- tool results are bounded and source-referenced.

Use the safest canonical Hermes extension mechanism available in the pinned version (MCP/custom tool/plugin/gateway integration). Do not invent an ad-hoc shell command protocol when a supported Hermes tool mechanism exists.

### 3. Product skills and agent behavior

Create versioned, testable LILOs agent skills/instructions for the product domains below. Skills must use canonical tools and approved facts/evidence.

#### GBP
Hermes must be able to:
- inspect current profile/business facts/website knowledge;
- inspect recent provider posts and LILOs drafts;
- identify a non-repetitive useful post topic;
- generate approval-ready post copy/CTA proposal;
- generate profile/service/product optimization recommendations from evidence;
- submit proposals into existing GBP approval workflows.

Hermes may not publish or edit Google directly.

#### SEO
Hermes must be able to:
- consume deterministic crawl/GSC/PageSpeed opportunities;
- explain why the opportunity matters;
- correlate evidence across crawl, GSC, GA4, and existing content;
- prioritize actions using evidence already produced by deterministic systems;
- turn accepted SEO opportunities into content/implementation proposals.

Hermes must not replace deterministic detectors or manufacture search evidence.

#### Content
Hermes must be able to:
- inspect existing content and approved business facts;
- consume an accepted SEO/content opportunity;
- create a grounded brief;
- generate a grounded draft/revision;
- optimize an existing page against the accepted evidence/brief without inventing claims;
- submit editorial/client approval through existing Content workflows;
- preserve source/fact references in AIExecution/audit history.

Publication remains LILOs/GitHub workflow-controlled.

#### Reviews
Hermes must be able to:
- draft grounded review responses;
- use deterministic risk classification as a hard guardrail;
- summarize review themes/trends for operator insight;
- never auto-publish restricted cases;
- submit response drafts into existing approval workflow.

#### Insights / cross-product analysis
Hermes must be able to execute a governed cross-source analysis for a client/location using current GSC, GA4, GBP, Reviews, Content, and crawl/SEO evidence and produce:
- what changed;
- likely evidence-backed drivers;
- what requires attention;
- prioritized recommended actions;
- links/references to the underlying LILOs evidence/proposals.

This must become an inspectable agent run, not an ungrounded narrative widget.

### 4. Agent run persistence and observability

Bind Hermes runs to existing LILOs workflow runs and AI executions. Add only the minimal persistence needed for the Hermes binding/event projection; do not duplicate workflow state.

Operator-visible run detail must include:
- owning organization/location;
- workflow/task/skill;
- Hermes run/session ID (safe display/reference);
- status;
- model/provider;
- started/completed timestamps;
- tool calls and outcomes;
- current approval wait state;
- stop/steer controls when supported;
- token/latency/cost metadata when available;
- final output/proposal references;
- normalized safe failure code;
- audit correlation.

Events must be bounded/retained by policy. Do not persist chain-of-thought/private reasoning. Persist structured lifecycle/tool/result events only.

### 5. Memory policy

Hermes session continuity may be used to improve multi-step work, but Hermes memory is not authoritative business truth.

Requirements:
- session namespace must be organization + location + task/skill scoped;
- cross-client memory leakage must be impossible by contract/test;
- approved LILOs business facts override Hermes memory;
- unapproved model observations cannot become durable business facts automatically;
- memory can retain workflow/session context and operator instructions only within configured retention policy;
- provide a deterministic way to reset/expire a scoped Hermes session without affecting other tenants.

### 6. Human approval and mutation boundary

Any action that can change a client-facing/provider-facing asset must remain a LILOs proposal followed by an existing LILOs approval/write workflow.

Examples:
- GBP post: Hermes proposal -> LILOs revision -> approval -> canonical publish workflow -> provider verification.
- Content: Hermes draft -> editorial/client approval -> canonical GitHub publication workflow.
- Review response: Hermes draft -> deterministic risk gate -> approval -> canonical provider publication workflow.
- SEO implementation: Hermes recommendation/proposal -> approval -> implementation task; no direct arbitrary production edit.

### 7. UI / operator experience

Extend the existing Automations/appropriate product surfaces rather than creating a disconnected agent console.

Required UX:
- start supported agent work from the relevant product/context;
- see live/refreshing run status and structured activity;
- inspect tool activity without exposing secrets or chain-of-thought;
- approve/deny requested gated actions;
- stop a running agent;
- steer a running agent when runtime capability is available;
- resume/revisit completed run history;
- navigate from run outputs directly to created GBP/Content/SEO/Review proposals;
- truthful loading/empty/error/degraded/capability-unavailable states.

No control may appear functional if the deployed Hermes capability is absent.

### 8. Scheduling and automation

Use the existing LILOs scheduler/workflow catalog. Do not use Hermes `/api/jobs` as a second scheduler for LILOs product work.

At minimum, make these existing recurring patterns agent-capable where appropriate:
- GBP post proposal generation;
- recurring cross-source client insight brief;
- accepted SEO opportunity -> content proposal processing;
- review-response proposal generation where policy permits.

All schedules remain LILOs-owned and tenant-scoped.

### 9. Runtime/deployment contract

Hermes deployment must:
- expose authenticated private endpoints needed for runs/events/approval/stop and steer transport;
- publish a detailed health/capability probe consumable by LILOs;
- pin/configure the governed model route on boot;
- fail closed when required model/provider/API credentials are absent;
- avoid exposing Hermes publicly;
- preserve persistent data only where required for session/skill state;
- show release/version/capability information sufficient to detect API/worker/Hermes skew.

If the Hermes version must be upgraded for a required supported capability, pin the tested version. Do not float an unpinned latest image.

### 10. Tests / acceptance scenarios

Required repository tests include at least:
1. Cross-tenant tool invocation is denied even if model supplies another org/location identifier.
2. Agent run binds to the correct LILOs workflow and Hermes run/session.
3. Structured event ingestion does not persist chain-of-thought or secrets.
4. Tool call audit records safe metadata and source references.
5. GBP agent creates a proposal only; cannot directly publish.
6. SEO agent consumes deterministic evidence and cannot establish unsupported facts.
7. Content agent produces a grounded brief/draft with fact/source references.
8. Review agent respects deterministic restricted-risk blocking.
9. Cross-product insight run reads real persisted evidence and produces linked recommendations/proposals.
10. Stop transitions an active Hermes run and reconciles LILOs state.
11. Approval round-trip works through LILOs policy.
12. Steer is delivered to the active Hermes run through a genuinely supported Hermes transport.
13. Missing Hermes capability is rendered unavailable, not silently simulated.
14. Scoped session reset does not affect another client/location.
15. Existing GBP/Content/Reviews one-shot governed generation remains regression-safe or is migrated without behavior loss.
16. Scheduler remains LILOs-owned; no Hermes job scheduler is used for product work.
17. Provider mutation remains exclusively through existing LILOs workflows.
18. Full repository validation passes.

### 11. Required live production acceptance

Repository green is not enough. After deploy, use a real acceptance client/location and prove:
- LILOs -> private Hermes run creation works;
- events/tool activity are visible in LILOs;
- Hermes reads approved business facts plus at least GBP + GSC/GA4 or crawl evidence through sanctioned tools;
- one real cross-product analysis completes;
- one real GBP or Content proposal is produced through the agent path;
- human approval remains required;
- one stop action works on a live test run;
- one steer action works on a live test run using the supported Hermes transport;
- no raw provider write can be initiated by Hermes;
- final audit/workflow history is complete;
- tenant isolation is explicitly tested with a second fixture/tenant scope;
- Render/API/worker/Hermes release/capability parity is visible.

Do not mark this packet accepted until those live checks pass.

## Validation discipline

- Inspect -> confirm root causes/gaps -> implement coherent batch -> focused validation -> one integrated repository validation.
- Never rerun an unchanged failing command.
- If the same validation fails twice, stop and diagnose.
- Do not change unrelated code to force green.
- No direct production SQL or provider mutation for acceptance setup.
- No hard-coded client names/IDs.

## Release ledger

Update the Hermes/AI, Automation & Agents, GBP, SEO, Content, Reviews, Insights, and overall release rows with exact repository and live evidence. Keep live status partial until production acceptance above is complete.

## Completion report

Return:
- confirmed current-state gaps;
- architecture chosen for Hermes runs and sanctioned tools;
- exact Hermes protocol/capabilities used (including steer transport);
- changed files/migrations;
- product skills/tools implemented;
- security/tenant isolation evidence;
- focused validation totals;
- integrated validation totals;
- commit SHA and push status;
- live acceptance checklist/status;
- remaining blockers, if any.

Do not merge until repository acceptance is green. Do not claim the Hermes agent layer complete until live production acceptance is green.