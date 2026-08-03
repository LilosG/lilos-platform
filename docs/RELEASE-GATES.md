# Release Gates

Mandatory CI gates are formatting, lint, type checking, frontend/Python tests, PostgreSQL integration and migration cycling, tenant/auth regressions, secrets, dependency audits, browser/accessibility, synthetic backup restore, build, environment contract, and acceptance-package completeness. Any missing gate fails closed. Production smoke, live monitoring, live backup restore, pilot, and human approvals remain external Phase 19 gates.
