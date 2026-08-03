# Disaster Recovery

Scenarios cover database/region/frontend/API/worker/scheduler/secret-store/monitoring/provider/DNS loss, bad migration, credential compromise, and corrupt backup. Default goals are proposals pending approval: RPO 24 hours and RTO 8 hours. Owners are operations with engineering and security escalation. CI proves synthetic restore; geographic failover and production recovery exercises are not claimed.
