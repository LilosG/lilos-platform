# LILOs Platform Consolidation & Productization — Commercial V1 Release

## Purpose

This release converts the existing LILOs codebase from a set of partially integrated product surfaces into one coherent commercial platform.

This is a consolidation/productization release. It is not a rewrite and not a license to create parallel architecture.

## Commercial operating modes

One platform supports:

### Managed by LILOs
LILOs configures and operates most of the account. The client completes only actions that legitimately require the client, such as authorization or confirmation.

### Co-Managed
LILOs preconfigures the account and client performs bounded setup, approvals, or day-to-day work.

### Self-Service
The customer can complete the same underlying onboarding and operate entitled modules directly.

These modes alter responsibility and permissions, not the underlying domain architecture.

## Required platform layers

### Agency Operating Layer
A portfolio-level operating surface for:
- clients;
- portfolio health;
- requires attention;
- today's work;
- approvals;
- automation health;
- reporting readiness;
- recent activity;
- administrative access.

### Client Workspace
A scoped, simplified surface for:
- account/business performance;
- required client actions;
- completed work;
- upcoming work;
- entitled products;
- automation activity where appropriate;
- integrations/settings the user's role may manage.

No unrelated provider resources or agency-only administration may appear.

### Modular Products / Entitlements
The UI and API respect enabled products and scope.

A single-module customer should not see a graveyard of disabled modules. A full-suite customer sees the integrated suite.

### Centralized Integrations
External provider setup is centralized.

V1 priority:
- Google: Business Profile, Search Console, Analytics.
- GitHub.
- Email/SMS delivery providers already supported by the repository.

Integrations owns:
connection/auth; provider accounts/resources; mappings; capabilities; credential health; sync/webhook state; connection ownership; privileged unmapped-resource queue.

Products show only concise dependency health and links to Integrations.

### Operational Products

#### Business Profile
Operational profile workspace: business information, categories/services, hours, posts, media, performance, recommendations, approvals/activity.

#### Reviews
Review inbox/status, response workflow, approvals, themes/performance, reconciliation.

#### SEO
GSC/GA4/crawler-informed performance, technical findings, local/search opportunities, recommendations, implementation/verification state.

#### Content
Opportunities, briefs, drafts, review, approval, publication workflow, deployment verification, performance.

#### Leads
Intake, routing, assignment, response/follow-up, consent/suppression, status, provider communication truth, conversion reporting.

#### Insights
Cross-product outcome reporting with periods, comparisons, source, freshness, quality state, completed work, recommendations, automation activity.

### Automation & Agents
A first-class control plane over the existing workflow/worker/scheduler architecture.

Agency surface:
- automation catalog;
- active/paused/attention states;
- schedule;
- last/next run;
- run history;
- approvals;
- failures/retries;
- audit/correlation;
- governed AI task execution;
- execution cost/usage where supported.

Client surface:
- understandable automation status/activity without internal diagnostics.

V1 automation patterns should exist across the suite where the existing architecture/product requires them: provider sync/monitoring, review ingestion/response workflow, SEO crawl/sync/opportunity analysis, content strategy/drafting/publication, lead response/follow-up, scheduled reporting.

### Governed AI
AI is embedded inside product workflows, not a standalone uncontrolled architecture.

AI tasks require grounded input, explicit schemas/outputs where applicable, validators, limits, permissions/approval policy, observable execution, and safe failure.

### Reporting
Reporting is an outcome layer, not raw analytics cards.

Client reporting should answer:
- What changed?
- What did LILOs do?
- What resulted?
- What needs attention?
- What happens next?

## Onboarding contract

One resumable flow:

Business → Locations → Products → Integrations → Resource Mapping → Configuration → Automation Defaults → Readiness → Activate.

Readiness must be derived from authoritative domain/integration state, not duplicated UI flags.

Provider information already verified may be reused but must remain reviewable/correctable.

## Information architecture target

Agency:
- Overview
- Clients
- Work / Approvals
- Products or client workspace entry
- Automation
- Reporting
- Integrations
- Settings / Administration

Client:
- Overview
- entitled operational products
- Automation (if entitled/appropriate)
- Insights/Reporting
- Settings
- Integrations (only capabilities the role may manage)

Exact labels may vary if repository conventions require it; responsibilities may not.

## UX quality target

Use the Glass Ops reference as a clarity benchmark, not a visual theme.

Required characteristics:
- obvious hierarchy;
- clear directory → detail pattern for integrations;
- high signal in first viewport;
- consistent cards/tabs/tables;
- intentional empty/error/loading states;
- actionable status language;
- setup is visible when blocking but does not dominate healthy product pages;
- no internal implementation vocabulary where plain operational language is possible.

## Release packets

### Packet 0 — Baseline and contract map
Principal reconciles current main, current deployments, migrations, product/read models, integration architecture, workflow architecture, and existing tests. Produces ownership map and dependency graph. No broad product code changes.

### Packet 1 — Platform information architecture
Agency/client boundaries, role/scope/entitlement-aware navigation, settings/integrations/automation placement, and removal of obvious provider/setup leakage from normal product IA.

Exit: navigation and page ownership communicate one coherent platform.

### Packet 2 — Unified onboarding
Managed, Co-Managed, Self-Service responsibility modes over one resumable engine. Shared business/location/product/integration/mapping/config/readiness path.

Exit: new account can reach activation without direct DB manipulation or separate inconsistent setup per product.

### Packet 3 — Integration control plane
Provider directory/detail workspaces, Google/GitHub/email/SMS configuration and health, privileged provider-resource mapping, confirmed product dependencies.

Exit: connect once, map once, consume everywhere.

### Packet 4 — Operational product convergence
GBP, Reviews, SEO, Content, Leads become focused operating workspaces consuming centralized integrations.

Exit: normal product pages primarily answer what can be done and what requires attention.

### Packet 5 — Automation & Agents
Productize existing workflow/worker/scheduler runtime and complete required V1 automation visibility/execution paths.

Exit: LILOs visibly performs durable scheduled/background work when no dashboard is open.

### Packet 6 — Insights & Reporting
Governed cross-product metrics, periods/comparisons/freshness, agency/client dashboards, completed work, automation activity, report workflow.

Exit: a client can understand outcomes and LILOs work from the platform.

### Packet 7 — Productization and release acceptance
Consistent UX, terminology, empty/error states, accessibility/responsive/browser acceptance, tenant-role acceptance, real integration acceptance, focused live writes where authorized, full release gate.

Exit: coherent controlled-pilot commercial V1.

## Parallelization

Do not parallelize before Packet 1 establishes shared boundaries.

After Packet 1:
- Integration Control Plane and Automation & Agents may proceed in isolated worktrees.
- Product UX may proceed in an isolated worktree only against frozen shared contracts/ownership.
- Unified onboarding may be integrated with Integrations work or run as a bounded branch after shared state contracts are frozen.
- Insights/Reporting begins after required product/integration data contracts stabilize.
- Final acceptance occurs only on the integrated release branch.

## V1 scope discipline

Do not add new unrelated providers/products during this release.

Deferred expansion may include additional CRMs, restaurant systems, rental systems, or generic new agent frameworks. Record opportunities in the ledger and continue the current release.

## Pilot vs formal GA

A controlled client pilot may be accepted when the V1 platform layers and pilot capabilities meet their live acceptance criteria and any unproven capability is explicitly disabled or marked blocked.

Formal GA additionally requires the governing production-readiness obligations such as backup/restore evidence, monitoring/alerts, rollback, production observation, and formal acceptance/signoff.

Do not conflate the two.
