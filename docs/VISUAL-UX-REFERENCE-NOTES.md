# Visual / UX Reference Notes

These notes translate the supplied current LILOs and Glass Ops screenshots into text usable by coding agents.

## Glass Ops reference — qualities to emulate

The reference is a quality and information-architecture benchmark, not a theme to copy.

Observed strengths:

- Persistent left navigation has obvious Operations vs Admin grouping and a clear active state.
- Dashboard first viewport immediately communicates meaningful KPIs and operational queues rather than setup machinery.
- Integrations & API Keys is a clean provider directory using consistent, easy-to-scan provider cards.
- Clicking a provider opens a focused provider detail page containing connection state, credentials/configuration fields where relevant, webhook/configuration information, and concise instructions.
- Provider setup is separated from operational product screens.
- Settings uses a clear tile/directory pattern.
- Calibration/work queue screen uses title/explainer, status tabs, filters/search, structured table, and intentional empty state.
- Information density is high without being confusing.
- Cards, tables, tabs, spacing, and empty states are consistent.

## Current LILOs screenshot — Insights

Observed:
- Scope shows Wheyland Electric and "Client workspace".
- KPI cards show Sessions, Users, Page Views, Conversions.
- A note says current totals lack period comparison because the reporting API does not return observation window/comparable prior period.
- Source cards show Google Analytics connected while Business Profile, Reviews, Content, and SEO show various blocked/setup states.
- Cross-product data simultaneously shows Business Profile locations/profile snapshots, Reviews responded count, and SEO crawl completed count.

Problems to trace, not mask:
- Contradictory readiness can show products as blocked even while product data exists.
- The product currently foregrounds setup/readiness state rather than business operation.
- KPI presentation needs period/comparison/source/freshness semantics where supported.
- Provider-resource counts must not masquerade as client-managed location counts.

## Current LILOs screenshot — GBP

Observed:
- Wheyland Electric client workspace shows Google connection as connected.
- One managed Wheyland location is visible.
- A large setup/discovered-locations section lists many unrelated businesses visible to the agency Google credential, including other LILOs clients/businesses.
- Each discovered resource has mapping controls.

Required product direction:
- Broad discovery/mapping belongs in privileged Integrations → Google → Available/Unmapped Resources.
- Normal Wheyland GBP should show Wheyland operational state only.
- Verify with a real client role. If unrelated resource names are visible to a client user, treat as a release-blocking tenant information exposure.
- If agency-only, it remains a major information-architecture problem and should not dominate a page labeled Client workspace.

## Target first viewport — agency

Prefer:
- outcome/portfolio KPIs;
- Requires Attention;
- Today's Work;
- approvals/automation issues;
- recent meaningful activity;
- portfolio/product health.

Integration setup becomes prominent only when it blocks work.

## Target first viewport — client

Prefer:
- Account Status;
- 3–5 real outcome KPIs;
- What Changed;
- Requires Your Attention;
- Work Completed;
- Upcoming;
- concise freshness/source state.

No agency diagnostics, raw provider discovery, or unnecessary implementation vocabulary.

## Integration mental model

Integrations owns external systems.

Example Google workspace:
- connection health;
- connected account;
- granted capabilities;
- GBP mapped resources;
- Search Console mapped property;
- GA4 mapped property;
- last sync/freshness by capability;
- provider resources available for mapping (privileged);
- reconnect only when credential/capability state actually requires it.

Operational products display a small dependency indicator and link back to Manage Integration.

## Automation mental model

A first-class Automation area should expose understandable work such as:
- GBP monitor/sync;
- review ingestion/response workflow;
- SEO sync/audit/opportunity work;
- content strategy/draft/publish;
- lead response/follow-up;
- scheduled reporting.

Show status, schedule, last/next run, result, approvals, and failures.

Agency admins may drill into workflow steps, model/cost, logs, retry, provider verification, and correlation/audit details.
