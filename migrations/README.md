# Database migrations

Alembic manages every PostgreSQL schema change. Configuration is loaded through the typed API
settings and requires `LILOS_MIGRATION_DATABASE_URL` or its `LILOS_DATABASE_URL` fallback.

Revision identifiers use the deterministic pattern `YYYYMMDD_NNNN`. The first revision is
`20260801_0001`. New migrations must document affected tables, constraints, indexes, compatibility,
data movement, and rollback or forward-fix behavior.

The baseline revision intentionally performs no domain DDL. Alembic's version table proves upgrade
and downgrade movement without introducing organizations, users, tenants, products, workflows, or
other business records.
