# Dependency and Supply-Chain Security

Lockfiles are authoritative. CI runs `npm audit --audit-level=high`, `pip-audit`, secret scanning, formatting, static analysis, tests, migrations, browser checks, and build validation. Critical vulnerabilities block release. Breaking upgrades require focused validation; no automatic dependency mutation is performed by the gate.
