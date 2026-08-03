# Phase 13 Route Authorization Matrix

| Surface | Permission | AAL | Scope |
|---|---|---:|---|
| Websites, pages, observations, opportunities, outcomes | `seo.read` | aal1 | organization/location |
| Property confirmation and crawl scope | `seo.manage` | aal2 | organization/location |
| Recommendation drafting | `seo.recommend` | aal1 | organization/location |
| Recommendation approval and execution request | `seo.approve`, `seo.execute` | aal2 | organization/location |

Permissions and assurance are fixed by server routes; there is no arbitrary crawler or permission-check endpoint.
