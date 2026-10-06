"""Create the private Supabase Storage buckets the platform needs. Idempotent.

Dry-run by default: it reports each bucket and changes nothing. ``--apply`` creates a missing
bucket as private. A bucket that already exists is never altered, and one that is public is
reported loudly, because a public bucket would expose client photos.

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.ensure_storage_buckets [--apply]
"""

from __future__ import annotations

import argparse

from apps.api.app.config import Settings
from apps.api.app.storage.objects import (
    GBP_MEDIA_BUCKET,
    StorageNotConfiguredError,
    SupabaseObjectStorage,
    object_storage,
)
from scripts._cli import EXIT_BAD_ENVIRONMENT, run_script

BUCKETS = (GBP_MEDIA_BUCKET,)
EXIT_PUBLIC_BUCKET = 4


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="create missing buckets as private")
    args = parser.parse_args()
    try:
        storage = object_storage(Settings())
    except StorageNotConfiguredError:
        print("error: LILOS_SUPABASE_URL and LILOS_SUPABASE_SERVICE_ROLE_KEY are required.")
        return EXIT_BAD_ENVIRONMENT
    assert isinstance(storage, SupabaseObjectStorage)
    exit_code = 0
    for bucket in BUCKETS:
        state = await storage.ensure_bucket(bucket, apply=args.apply)
        if state == "public":
            exit_code = EXIT_PUBLIC_BUCKET
        suffix = "" if args.apply or state != "missing" else " (dry run; pass --apply to create)"
        print(f"{bucket}: {state}{suffix}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run_script("ensure_storage_buckets", main))
