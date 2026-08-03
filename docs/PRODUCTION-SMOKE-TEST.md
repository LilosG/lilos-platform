# Production Smoke-Test Plan

The safe sequence is frontend load; liveness/readiness; authentication and organization selection; authorized read and generic denial; cross-tenant not-found sample; worker/scheduler heartbeat; deterministic no-op durable job; approved test notification; provider health and sync dry-run; controlled/disabled AI check; dashboard/report; audit append; alert path; backup freshness; runtime pause; and maintenance mode recovery.

Use only an approved pilot and synthetic/test destinations. Do not perform irreversible provider writes. Capture release, correlation IDs, times, outcomes, and incidents without customer data or secrets. Production smoke status is pending because no production environment exists.
