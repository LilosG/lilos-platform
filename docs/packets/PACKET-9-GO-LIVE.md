# Packet 9 — Go Live

**Branch:** `packet/9-go-live` off `main` after Packet 4 merges
**Builder:** DeepSeek V4 Pro
**Type:** Deployment and live verification. No new features.

Everything to date is `IMPLEMENTED_NOT_ACCEPTED` because acceptance has been unit tests and fixtures. This packet converts that to live acceptance against Wheyland Electric.

**Stop conditions:** a secret you cannot obtain, a customer-visible provider write, an external account permission, or a live failure whose root cause is a missing backend capability. Everything else, decide and continue.

---

## 1. Merge and deploy

Merge `packet/4a-seo-crawl-engine` and `packet/4-product-convergence` to `main` through PRs. Confirm CI green on `main`.

Apply migrations to production through the migration path — never direct SQL. Head must reach `20260813_0001`. Record the revision before and after.

Deploy API, worker, and scheduler to Render; frontend to Vercel. Confirm all four are running the same commit SHA and record it. Confirm the worker and scheduler processes are actually alive, not just deployed.

## 2. Database-backed tests must run

395 pytest tests currently skip for want of `LILOS_TEST_DATABASE_URL`. That is most of the tenant-isolation, provider-reconciliation, and workflow coverage in the repository.

Configure an isolated test database in CI and make those tests run on every push. Report how many previously-skipped tests now run and how many fail. Fix what fails or record it precisely.

## 3. Google connection

Against the real Wheyland Electric organization, connect Google once and confirm:

- All granted scopes present after one consent
- Reload, navigate away, return: no repeat consent prompt on a healthy credential
- Token refresh works — verify the refresh path executes, do not wait for natural expiry
- Connection health reports accurately in Integrations

If consent re-prompts on a healthy credential, that is a defect in lifecycle code, not a reason to touch Google Cloud configuration.

## 4. Provider read acceptance

For Wheyland's confirmed location, verify each of these against live data and record what came back:

- GBP profile and location sync
- Reviews ingestion, reconciled against what Google actually shows
- Search Console sync: property mapped, data landing, periods correct
- GA4 sync: property mapped, sessions/users/page views/conversions landing
- Insights renders live figures with real comparisons and freshness — not fixtures

## 5. SEO crawl — SC4A-DISCOVERY

Run a real crawl of wheylandelectric.com through the deployed worker.

- **State the page count.** More than one page is the pass condition; the previous implementation crawled exactly one.
- Confirm the API returns promptly with a run reference while the crawl continues in the worker — that is SC4A-DURABLE, also never proven live
- Confirm page inventory persists with the full field set
- Confirm opportunities are created from technical issues
- Run at `max_pages` 25 and again at 250; confirm both bind and record the stop reason
- Sitemap-vs-crawl comparison produces its three categories

Crawl only wheylandelectric.com. No other client site.

## 6. Client-role isolation

Create a client-role login for Wheyland and sign in as that user, not as an operator with a filter applied.

- Only Wheyland data is visible
- No admin navigation, no Administration, no Client Onboarding
- Attempt to read another organization's data by direct URL and by API — both must fail
- No unmapped provider resources, no other organizations, no cross-tenant anything

**Any cross-client visibility is a release blocker.** Stop and report.

## 7. One provider write

Publish one real review response for Wheyland through the product, with owner approval before it goes out.

Verify: idempotency held, the provider re-read confirms the write, reconciliation matched, audit recorded it, and the UI reflects the true published state.

This is the only customer-visible write in this packet.

## 8. Leads truthfulness

`LeadCommunication` marks `sent` when a notification is queued, not when a provider dispatched it. Determine on live infrastructure whether real dispatch occurs.

If it does not, the Leads product must say setup required and outbound stays disabled for the pilot. Do not present queueing as delivery, and do not report speed-to-lead timing measured from a queue event.

## 9. Automations

Confirm at least one workflow schedule is registered and active in the production database, that the scheduler fires it, that a run completes, and that history and failure states surface truthfully in the product.

If no schedule is active, say so — the ledger has recorded "no evidence of active schedules" since the baseline and it has never been resolved.

## 10. Production readiness

Backup and restore verified, not assumed. Error monitoring receiving events. Secrets server-side and absent from logs and frontend responses. Health endpoints accurate. Rate limits and timeouts sane under real provider latency.

---

## Acceptance

The pilot is live when, for Wheyland Electric, every item above passes against production with no SQL and no manual backend step, and the ledger is updated to `LIVE_READ_ACCEPTED` or `LIVE_WRITE_ACCEPTED` per capability with the evidence that justifies it.

Report per section: what was run, against what, what came back. State the crawl page count plainly. Name every failure and its root cause.

Do not mark anything accepted that was not observed against live data.
