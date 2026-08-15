# SC4-STATUS-OWNERSHIP audit

Connection and provider health are owned by Integrations. Overview, Insights,
and Settings contain only compact links to that owner and do not fetch or
render product readiness matrices.

Command:

```sh
rg -n "fetchProductReadiness|summarizeReadiness|Website readiness|Cross-product metrics|Connection status|Operational readiness" apps/web/src/pages/index.astro apps/web/src/pages/insights.astro apps/web/src/pages/settings.astro
```

Result: no matches.

The provider workspace remains in `apps/web/src/pages/integrations.astro`.
