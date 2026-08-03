# Phase 15 Route Authorization Matrix

| Surface | Permission | AAL |
|---|---|---:|
| Metrics, dashboards, goals, report revisions | `insights.read` | aal1 |
| Goals, annotations, report definitions | `insights.manage` | aal1 |
| Report approval, delivery, export | `insights.publish` | aal2 |

All queries are server-scoped; no raw SQL or arbitrary metric-definition endpoint is exposed.
