#!/bin/sh
set -eu

export LILOS_RELEASE="${RENDER_GIT_COMMIT:?RENDER_GIT_COMMIT is required}"

alembic upgrade head

export LILOS_DATABASE_URL="$LILOS_MIGRATION_DATABASE_URL"

python -m scripts.seed_industries
python -m scripts.seed_access_catalog
python -m scripts.seed_administration_catalog
python -m scripts.seed_integration_providers
