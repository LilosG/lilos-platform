# Scripts

Repository maintenance scripts live here. Scripts must be deterministic, documented, and must not
contain credentials or make unapproved external changes.

`npm run db:seed:industries` runs the explicit, transactional initial-industry seed against
`LILOS_DATABASE_URL`. It is idempotent for matching records, reports name mismatches, does not
silently change existing policy JSON, and creates industry audit events through the application
service. Apply migrations first and never point it at an unapproved database.
