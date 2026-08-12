# LILOs Platform Release Ledger

This ledger is updated by the principal release integrator from repository and live evidence.

## Status vocabulary

- `NOT_STARTED`
- `IMPLEMENTED_NOT_ACCEPTED`
- `LIVE_READ_ACCEPTED`
- `LIVE_WRITE_ACCEPTED`
- `PILOT_READY`
- `BLOCKED_EXTERNAL`
- `DEFERRED_POST_PILOT`

Do not mark a capability more complete than the available evidence.

## Baseline

**Round 0 verified baseline:**
- Branch: `release/platform-consolidation`
- SHA: `35cf577813480da7869f6917fcf82f2f12a2230e`
- Parent (main): `65c51f4dfd0a3d9a7642a68814a58c21679038eb`
- Working tree: clean
- Migration head: `20260811_0002_gbp_media_safe_error_code` (32 total migrations)
- Vercel deployment: rate-limited (PR #15 deployment blocked; PR #14 deployed successfully)
- Render API/worker/scheduler: deployment parity not verified live (requires runtime access)

## Capability ledger

The **Implementation** column uses the formal status vocabulary. The **Live acceptance**, **UX / productization**, **Automation**, and **Reporting** columns use evidence-backed qualifiers:
- A formal status (e.g., `IMPLEMENTED_NOT_ACCEPTED`) where the column represents a distinct acceptance dimension.
- `n/a` — not applicable to this capability.
- `partial` — some evidence exists but the dimension is not complete (equivalent to `IMPLEMENTED_NOT_ACCEPTED` for that dimension).
- `unknown` — no live evidence available; requires runtime access to verify.

| Layer / capability | Implementation | Live acceptance | UX / productization | Automation | Reporting | Current blocker / evidence |
|---|---|---|---|---|---|---|
| Agency operating layer | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Dashboard renders KPIs + attention + work from real data; needs first-viewport convergence per Packet 4/6 |
| Client workspace | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | partial | partial | **P0: Client role scoping unverified.** Navigation hides Admin group via `hidden` attribute (frontend-only). GBP page renders unmapped provider resources. Client role live test required. |
| Entitlement-aware navigation | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | Navigation groups defined in `platform.ts`; Admin group hidden via `hidden` attribute. Backend authorization enforces per-request. Frontend does not pre-filter by role. |
| Unified onboarding | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | readiness partial | `OnboardingOrchestrationService` composes 8 steps + per-product readiness. Managed/Co-Managed/Self-Service responsibility modes not yet differentiated in UI. |
| Google connection lifecycle | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync partial | health partial | `GBPConnectionService` handles full OAuth lifecycle with incremental scopes. PR #10 repaired reconnect logic. Live acceptance: healthy connection must not re-prompt OAuth (unverified). |
| Google provider resource mapping | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | **P0: Broad discovery rendered on GBP page labeled "Client workspace".** `gbp.astro` lines 371-446 render ALL unmapped locations regardless of client scope. Mapping queue belongs in privileged Integrations workflow. |
| GBP operational product | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync/media/post workflows partial | partial | GBP models/services/routes fully implemented. 9 workflow handlers registered including `gbp.sync`, `gbp.publish_change`, `gbp.publish_post`, `gbp.upload_media`. Live evidence: Wheyland has 1 managed synced location + 90 reviews. Provider writes fail-closed by default. |
| Reviews | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | ingestion/reply workflow partial | partial | Review models/services/routes fully implemented. `reviews.ingest` and `reviews.publish_response` handlers registered. Live evidence: 90 reviews reconciled/responded for Wheyland. |
| Search Console | IMPLEMENTED_NOT_ACCEPTED | unknown | IMPLEMENTED_NOT_ACCEPTED | sync unknown | partial | `SearchConsoleService` with discovery, mapping, sync. `SearchConsoleAdapter` for API calls. Live mapping/sync/freshness unverified. |
| GA4 | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync unknown | IMPLEMENTED_NOT_ACCEPTED | `AnalyticsService` with discovery, mapping, sync. Live metrics visible (Sessions 764, Users 576, Page Views 1201, Conversions 58). **Known gap: no period/comparison.** Insights page explicitly notes: "Current totals are shown without a period comparison because the reporting API does not yet return an observation window or comparable prior period." |
| SEO | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | SEO models/services/routes fully implemented. `seo.crawl_or_analysis` handler registered. Live crawl/GSC/recommendation lifecycle unverified. |
| Content | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Content models/services/routes fully implemented. `content.publish` handler registered. GitHub App installed for Wheyland. **Known blocker: 1 business fact needs confirmation through UI.** |
| Leads | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Lead models/services/routes fully implemented. `leads.send_communication` handler registered. **Status semantics gap: `sent` status may mean notification queued, not provider-dispatched.** `LeadCommunication` model has proper states (planned→queued→sent→delivered) but handler creates notification delivery records; actual provider dispatch delegated to notification delivery jobs. Live verification required. |
| Integrations control plane | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | health partial | Integration models/services/routes implemented. Integrations page exists. Needs central directory/detail/mapping convergence per Packet 3. |
| Automation & Agents control plane | IMPLEMENTED_NOT_ACCEPTED | n/a | NOT_STARTED | IMPLEMENTED_NOT_ACCEPTED | NOT_STARTED | 9 workflow handlers registered. Worker/scheduler runtime functional. **No evidence of active schedules in database.** Automation catalog/surface not yet productized. |
| Insights / reporting | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | scheduled reporting partial/unknown | IMPLEMENTED_NOT_ACCEPTED | `InsightsService.summary()` aggregates real product data. **Known issues: (1) `gbp.locations` counts ALL GBPLocation rows including unmapped — "17 locations" may include non-Wheyland resources. (2) No period/comparison for GA4 metrics. (3) Contradictory readiness: products show "blocked" while product data exists.** |
| Release/production acceptance | IMPLEMENTED_NOT_ACCEPTED | partial | n/a | n/a | n/a | **Vercel deployment rate-limited for current main.** PR #14 deployed successfully. Render API/worker/scheduler parity unverified. Migration head `20260811_0002` deployment status unknown. Backup/restore evidence not verified. |

## Round 0 findings

### Confirmed architecture present
- Full FastAPI modular monolith: 23 service domains + 7 product modules
- Astro frontend: 13 page routes, 47 lib modules
- PostgreSQL-backed workflow engine: 9 registered handlers, worker/scheduler runtime
- Complete auth/authz stack: Supabase JWT, role-based access control, tenant isolation
- Google OAuth lifecycle: incremental scopes, token refresh, credential health
- 32 Alembic migrations covering full schema evolution
- ~150+ Python test files, vitest unit tests, Playwright browser tests
- Render deployment (API, worker, scheduler), Vercel deployment (frontend)

### Confirmed gaps (evidence-backed)

1. **P0 — Client scope leakage:** `gbp.astro` renders ALL unmapped discovered locations on a page labeled "Client workspace." The `InsightsService.summary()` counts ALL `GBPLocation` rows including unmapped ones. If a real client role can see unrelated business names, this is a release-blocking cross-client information exposure.

2. **P0 — Contradictory readiness:** Products show "blocked" with "Create the location profile" while product data (synced locations, 90 reviews) exists. Root cause: readiness engine checks `LOCATION_PROFILE_MISSING` independently of whether GBP data is already synced and mapped.

3. **P1 — Navigation admin leakage:** Admin group hidden via `hidden` HTML attribute (frontend-only). Client can still navigate to `/administration` and receive 403. Backend authorization is correct; UX contract violation.

4. **P1 — Insights metric semantics:** `gbp.locations` count includes unmapped provider-discovered resources. "Managed locations" label is misleading when count includes non-client businesses.

5. **P2 — GA4 period/comparison missing:** Insights page explicitly documents this gap. Reporting API does not return observation window or comparable prior period.

6. **P2 — Lead communication status semantics:** `sent` status may mean notification queued rather than provider-dispatched. Handler creates `NotificationDelivery` records; actual dispatch is delegated. Live verification required.

7. **P2 — No active automation schedules:** 9 handlers registered but no evidence of active `Schedule` rows in database for `gbp.sync` or `reviews.ingest`.

8. **P3 — Vercel deployment rate-limited:** Current main deployment blocked. Operational resolution required, not a code fix.

9. **P3 — Render deployment parity unverified:** Cannot confirm API/worker/scheduler are running current SHA without runtime access.

### Highest-risk cross-cutting issues

1. **Client scope leakage (P0):** Must be resolved before any client login is issued. Affects GBP page, Insights aggregation, and navigation.
2. **Contradictory readiness (P0):** Undermines trust in the platform's operational state. Affects all product pages and onboarding.
3. **Shared contract instability:** Navigation, readiness, and aggregation contracts must be frozen before parallel work begins.

## Packet acceptance log

### Packet 0 — Baseline and Contract Map
- Branch / commit: `release/platform-consolidation` / `35cf577`
- Auditor result: PENDING (run after deliverables created)
- Principal result: IN PROGRESS
- Focused checks: Repository structure mapped, domain trace complete, ownership boundaries defined
- Live checks: Not applicable (read-only round)
- Ledger rows changed: All rows updated from evidence
- Remaining blockers: Vercel rate-limit (operational), Render parity unverified (needs runtime access)
- Accepted: PENDING (awaiting auditor review)

---

## Known baseline questions — Round 0 answers

| Question | Answer |
|----------|--------|
| Exact current main SHA and clean/dirty state | Branch `release/platform-consolidation`, SHA `35cf577`, clean tree. Parent main at `65c51f4`. |
| Exact frontend/API/worker/scheduler deployed SHAs | Not verifiable without runtime access. PR #14 Vercel deployment green. PR #15 Vercel rate-limited. Render parity unknown. |
| Current migration head and deployed DB migration state | Head: `20260811_0002_gbp_media_safe_error_code`. Deployed DB state unknown without runtime access. |
| Real agency-role and real client-role navigation/scoping | Not tested live. Code inspection shows Admin group hidden via `hidden` attribute (frontend-only). |
| Whether client users can see unrelated Google provider resources | **High risk: YES, based on code inspection.** `gbp.astro` renders all unmapped locations. Live client-role test required. |
| Source and semantics of "17 locations" metric | `InsightsService.summary()` counts ALL `GBPLocation` rows for org, including unmapped. Likely includes non-Wheyland resources from agency Google credential. |
| Source of contradictory "Create the location profile" readiness | `AdministrationService.readiness()` checks `LOCATION_PROFILE_MISSING` independently of GBP sync state. Location profile may exist but not be linked to GBP location. |
| Current Google granted capabilities | Not verifiable without runtime access. Code supports GBP + GSC + GA4 scopes. |
| Current GSC and GA4 confirmed mappings, sync timestamps | Not verifiable without runtime access. GA4 metrics visible in screenshots. GSC state unknown. |
| Current workflow/schedule catalog and active handlers | 9 handlers registered. No evidence of active `Schedule` rows in database. |
| Lead email/SMS actual provider-dispatch and delivery semantics | `LeadCommunication.status` supports planned→queued→sent→delivered. Handler sets `sent_at` but delegates dispatch to notification delivery jobs. Live verification required. |
| Current reporting read models and period/comparison/freshness | `InsightsService.summary()` aggregates real data. GA4 metrics lack period/comparison. `MetricObservation.quality_state` enum supports data-quality states. |
| Current release-gate failures and genuine external blockers | Vercel rate-limit (operational). No code-level release gate failures identified. |