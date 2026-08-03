#!/bin/sh
set -eu

alembic upgrade head

export LILOS_DATABASE_URL="$LILOS_MIGRATION_DATABASE_URL"

python -m scripts.seed_industries
python -m scripts.seed_access_catalog
python -m scripts.seed_administration_catalog
