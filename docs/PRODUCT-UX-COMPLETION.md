# Product + UX Completion Handoff

This release pass turns the frontend into an organization-scoped operating workspace while preserving the API as the authorization and provider-truth authority. It does not add frontend-only success states, tenant exceptions, credentials, or mock production data.

## Surface acceptance

| Surface | Daily purpose | Completion highlights |
| --- | --- | --- |
| Shared shell | Keep client, organization, role, and navigation context visible | Agency/client audience label, platform-admin-only navigation, protected account label, responsive navigation drawer, active state, mobile organization/session controls |
| Overview | Answer what is happening and what needs action | Real operational KPIs, failures and blockers, today's queues, GA4 observations when present, recent activity, secondary location/product health |
| Business Profile | Operate one confirmed mapped location | Managed versus discovered locations, source verification/freshness, location switching, profile/hours/posts/media governance, Google-observed post reconciliation |
| Reviews | Triage and respond without duplicates | Rating and response KPIs, freshness, sentiment/risk queue, provider-observed reply provenance, draft/AI/approval/publish states and failures |
| Leads | Work the response queue | Open/urgent/assignment/conversion KPIs, lead age and response state, safe assignee labels, lifecycle actions, tasks/notes, provider-recorded delivery states |
| Content | Move work from opportunity through publication evidence | Pipeline detail, governed-fact readiness, briefs, manual/assisted revisions, editorial/client approval, repository-name target selection, publication/failure state and activity |
| SEO | Turn crawl evidence into governed work | Website context, crawl state, prioritized queue, readable evidence, recommendations and approvals, implementation state, Search Console source freshness |
| Insights | Report real cross-product results | GA4 metrics and sync source, explicit missing-period limitation, operational source readiness, status-derived product activity, no invented trend |
| Settings | Organize durable client configuration | Business, locations, website, users/access, governance/approvals, and organization-specific product readiness; client-safe empty states |
| Integrations | Explain provider capability and required action | Google service authorization, reconnect versus incremental authorization, connection verification, protected identifiers, repository names, confirmed disconnect consequences |
| Administration | Support agency portfolio operations | Lifecycle portfolio KPIs, client management, product readiness/entitlements, guided-onboarding entry, platform-admin presentation boundary |
| Client onboarding | Guide setup through handoff | Nine-step navigation, resumable readiness, consequence confirmation, activation, then provider connection/resource mapping/product handoff |
| Authentication and MFA | Establish and step up a secure session | Branded sign-in, clear status/error regions, authenticator guidance, focusable labelled inputs, explicit lost-factor limitation |

All surfaces use explicit loading, empty, error, blocked/degraded, success, and authorization outcomes where the current endpoint exposes them. Tables use real action buttons rather than pointer-only rows. Tabs provide arrow/Home/End keyboard behavior and complete tab/tabpanel relationships.

## API requirements for release integration

These are evidence-backed limitations in current frontend-consumed contracts. The frontend intentionally does not guess around them.

1. Agency home aggregation: `GET /api/v1/organizations/{id}/insights/summary` is organization-scoped and cannot provide portfolio health, scheduled work, billing/setup issues, or pending approvals across clients. Add an authorized agency portfolio summary with per-client attention counts and freshness.
2. Reporting periods and comparisons: the Insights `ga4` object and Search Console summary return totals and sync timestamps but no observation start/end, timezone, comparison period, or deltas. Add explicit period metadata and comparable prior observations before the UI renders trends.
3. Review inbox identity: the review list returns rating/status/sentiment/risk/provider/timestamps but no reviewer-safe display name or body excerpt. Add privacy-reviewed list fields so operators can distinguish rows without opening each review.
4. Membership display labels: membership lists expose `user_profile_id`, membership type, and status but no safe name/email label. Add an authorized display label to make Users & Access rows distinguishable without showing IDs.
5. Lead queue identity and source: the intentionally PII-free lead list has no safe display label or source name. Add an opaque/human queue label and safe source label if the product should identify rows before opening protected detail.
6. Lead currency: `converted_value_cents` has no currency code in the lead contract. Return the organization currency (or a money object) before the frontend can render a currency symbol truthfully.
7. Assignee names: the assignee picker permits `display_name: null`. Require or provide a safe fallback label from the API; the frontend currently says “Unnamed … teammate” and never exposes a profile ID.
8. Publishing capability: content APIs expose targets and publication records but no accepted publishing connector capability/health endpoint. Add provider capability, last verification, required action, and executable availability so the UI can distinguish “target configured” from “publishing accepted.”
9. Approval/schedule aggregation: product summaries expose status counts but do not consistently expose pending client approvals or upcoming scheduled work with due times. Add a cross-product work-feed contract for the client and agency home variants.
10. Freshness consistency: GBP locations and GA4/Search Console properties expose sync timestamps/status, while review summaries and several product summaries do not. Add a common source observation shape (`observed_at`, `synced_at`, `freshness_status`, `quality_status`, `source`) to each reporting surface.
11. Content grounding requirements: brief creation requires approved fact revision IDs, but the frontend has to mirror the Content catalog’s required fact keys and resolve them one by one. Return the required keys and resolved active revisions as a product-scoped authoring contract so catalog changes cannot drift from the brief workflow.

## Integration guidance

- Preserve the frontend's fail-closed behavior when provider/runtime changes land. A non-OK response must remain an error, restricted, or degraded state—not “not connected” or zero.
- If the release-integrator changes summary or provider contracts, update the typed shapes in `apps/web/src/lib` and the Overview/Insights source-period copy together.
- Keep platform authorization authoritative. Navigation visibility is presentation only; it does not replace route enforcement.
- Re-run authenticated browser acceptance against real release APIs after provider OAuth/resource mapping is completed. Controlled frontend visual fixtures do not constitute provider acceptance.
