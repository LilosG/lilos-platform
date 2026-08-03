# Infrastructure Inventory

| Component | Required production property | Current evidence |
| --- | --- | --- |
| Frontend, API, worker, scheduler | Immutable artifacts and service identities | Deployment contract only |
| PostgreSQL 17 | Private network, encryption, backups/PITR, monitoring | Disposable PG17 validation only |
| Secret manager | Least privilege, rotation, audit | Interface documented; provider pending |
| Artifact storage | Immutable release and report artifacts | Provider pending |
| Telemetry | Logs, metrics, traces, dashboards, alert sink | Schemas/catalogs implemented; destination pending |
| Domains/TLS/DNS | Canonical frontend/API/OAuth hosts and renewal | Authority pending |
| Backup destination | Encrypted retention and restore environment | Synthetic restore proven; production destination pending |

No production resource is represented as provisioned by this inventory.
