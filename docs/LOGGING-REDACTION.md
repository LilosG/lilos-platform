# Logging and Redaction Standard

JSON events contain timestamp, severity, service, environment, release, correlation/trace identifiers, safe scoped identifiers, operation, outcome, error code, duration, and retry count. Values are defensively copied, strings are capped at 512 characters, objects and arrays at 32 entries, and nesting at five levels. Tokens, authorization, cookies, passwords, secrets, OAuth material, email, phone, customer content, connection strings, and raw payloads are replaced with `[REDACTED]`. Redaction occurs centrally before serialization.
