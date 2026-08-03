# CRM Lead Contract

CRM adapters exchange stable external identity, normalized status, content hashes, capability and freshness metadata. Platform and CRM state remain separate. Concurrent changes create a conflict document; newer provider state is never silently overwritten. Push intent uses Phase 5 jobs, Phase 7 connections, Phase 8 synchronization/idempotency, and deterministic test adapters. No vendor-specific CRM ships in Phase 11.
