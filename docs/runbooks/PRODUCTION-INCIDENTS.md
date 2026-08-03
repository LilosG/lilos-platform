# Production Incident Runbooks

For every event: preserve evidence, declare impact and severity, bind a correlation/incident ID, avoid destructive action, activate the narrowest runtime control, communicate through the approved channel, verify recovery, and retain the timeline.

| Failure | Detect and diagnose | Mitigate, recover, verify |
|---|---|---|
| API or database outage | readiness, pool, locks, recent release | maintenance mode; restore service; verify read/write and audit |
| Failed migration | head/drift/lock evidence | stop rollout; restore pre-migration backup or forward-fix; verify triggers |
| Queue, worker, scheduler | depth, heartbeat, leases | pause dispatch; recover stale leases; prove idempotent completion |
| Provider/OAuth/notification/AI outage | circuit, refresh, timeout, backlog | provider pause; bounded retry; reconcile; verify no duplicate action |
| Publishing or sync ambiguity | intent, provider reference, verification | prohibit blind retry; reconcile observed state |
| Audit-integrity failure | trigger and append test | emergency read-only; preserve evidence; restore controls before writes |
| Backup or restore failure | freshness, checksum, restore logs | block release; repair destination; perform synthetic restore |
| Certificate or DNS failure | expiry and resolution probes | restore approved record/certificate; verify callback exactness |
| Suspected isolation or credential exposure | access and telemetry evidence | emergency pause, revoke/rotate, preserve logs, security escalation |
| Authorization anomaly or owner lockout | denial trend and owner invariant | no bypass; use approved recovery with AAL2 and audit |
| Deployment rollback | release and health deltas | deploy prior immutable artifact; prefer forward DB remediation |

Escalation owners: operations primary, security for isolation/credentials, engineering for code/data, product/business for impact. Contact identities and destinations are supplied only by the production secret/incident system.
