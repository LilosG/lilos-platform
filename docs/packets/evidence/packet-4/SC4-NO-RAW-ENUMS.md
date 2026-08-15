# SC4-NO-RAW-ENUMS audit

Command:

```sh
rg -n "pending_verification|never_synced|setup_required|mapping_status|ownership_status" apps/web/src/pages apps/web/src/lib
```

Result: zero client-facing raw enum strings. Every remaining source occurrence
is disposed below. Tests are under `apps/web/src/lib`, so the requested grep
includes them.

| File and line(s)                                                                       | Disposition                                                                                                                |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `apps/web/src/lib/reporting.ts:223`                                                    | Contract comparison used to return “Not yet synced”; not rendered verbatim.                                                |
| `apps/web/src/lib/gbp.ts:14,35,82`                                                     | Existing API response field and validation/write response contracts; not presentation copy.                                |
| `apps/web/src/lib/status-language.test.ts:7-9,25-26`                                   | Tests proving the raw contract values map to client labels and tones.                                                      |
| `apps/web/src/pages/administration.astro:523`                                          | Source comment naming the lifecycle value.                                                                                 |
| `apps/web/src/pages/administration.astro:788`                                          | Control-flow comparison; rendered copy uses “initial setup state” / shared labels.                                         |
| `apps/web/src/pages/onboarding.astro:1430,1434`                                        | Source comments naming the lifecycle value.                                                                                |
| `apps/web/src/lib/platform-admin.ts:15,201`                                            | Existing TypeScript contract unions.                                                                                       |
| `apps/web/src/lib/platform-admin.ts:251,479`                                           | Source comments documenting backend semantics.                                                                             |
| `apps/web/src/lib/platform-admin.ts:256`                                               | Internal selected-status set; not presentation copy.                                                                       |
| `apps/web/src/lib/seo.ts:29,38`                                                        | Existing TypeScript response field names; values render through shared status language.                                    |
| `apps/web/src/lib/product-entitlements.ts:57,60-61,99,118,193,212`                     | Source comments documenting the existing lifecycle contract.                                                               |
| `apps/web/src/lib/product-entitlements.ts:223`                                         | Required existing transition request field/value; no contract change.                                                      |
| `apps/web/src/lib/status-language.ts:33,41,54`                                         | The centralized raw-to-client-label dictionary itself.                                                                     |
| `apps/web/src/lib/status-language.ts:121,124`                                          | Internal tone classification; not presentation copy.                                                                       |
| `apps/web/src/lib/product-entitlements.test.ts:21,36-38,58,86,106,121,126,129,137,145` | Contract fixtures and assertions for entitlement lifecycle behavior.                                                       |
| `apps/web/src/lib/platform-admin-entitlements.test.ts:41,98,137,146,156,172,179`       | Contract fixtures/assertions for the existing admin entitlement API. Audit reasons in these tests use human-readable copy. |
| `apps/web/src/lib/gbp.test.ts:11,30`                                                   | Contract fixtures verifying confirmed vs suggested mapping behavior.                                                       |

The status rendering path is centralized in
`apps/web/src/lib/status-language.ts`; the fallback also replaces underscores,
so unknown contract values do not leak raw separators.
