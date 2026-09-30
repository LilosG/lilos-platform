"""Dry-run the site-change executor's file resolution against a local checkout.

Reads the mapped files, resolves the current value, applies a proposed
change entirely in memory, and prints a unified diff of exactly what would
change. Never touches git, never opens a pull request, never writes to the
checkout on disk -- this is the resolver's URL -> file -> field proof, run
before any PR-writing path is exercised.

Usage:

    uv run python -m scripts.site_change_dry_run \\
        --repo-path /path/to/local/coco-maya-checkout \\
        --page brunch \\
        --field seo_title \\
        --proposed-value "New SEO Title Under Sixty Characters"
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

from apps.api.app.products.seo.change_set import SiteChangeField
from apps.api.app.products.seo.errors import SEOSiteMappingRequiredError
from apps.api.app.products.seo.site_map_resolver import (
    KeystaticJsonLocator,
    SiteMapEntry,
    apply_change,
    resolve_current_value,
)

# Reference page map for LilosG/coco-maya. Real client page maps are stored
# per publishing target (B4's follow-up); this literal map is the dry-run
# proof for the milestone's acceptance walkthrough (org
# 63fbf279-d214-4bca-8381-9f7bd70ae090, website 966ba1e8-4069-4499-ba23-b980700b7a37).
COCO_MAYA_PAGE_MAP: dict[str, SiteMapEntry] = {
    "brunch": SiteMapEntry(
        url_path="/brunch",
        fields={
            SiteChangeField.SEO_TITLE: KeystaticJsonLocator(
                file_path="src/content/brunchPage.json",
                json_pointer=("singleton", "seo", "title"),
            ),
            SiteChangeField.META_DESCRIPTION: KeystaticJsonLocator(
                file_path="src/content/brunchPage.json",
                json_pointer=("singleton", "seo", "descriptionTemplate"),
            ),
        },
    ),
}


def _load_files(repo_path: Path, entry: SiteMapEntry) -> dict[str, str]:
    files: dict[str, str] = {}
    for locator in entry.fields.values():
        full_path = repo_path / locator.file_path
        if not full_path.is_file():
            continue
        files[locator.file_path] = full_path.read_text()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-path", required=True, type=Path)
    parser.add_argument("--page", required=True, choices=sorted(COCO_MAYA_PAGE_MAP))
    parser.add_argument(
        "--field", required=True, choices=[f.value for f in SiteChangeField]
    )
    parser.add_argument("--proposed-value", required=True)
    args = parser.parse_args()

    entry = COCO_MAYA_PAGE_MAP[args.page]
    field = SiteChangeField(args.field)
    locator = entry.fields.get(field)
    if locator is None:
        print(f"No mapping for field {field.value!r} on page {args.page!r}.", file=sys.stderr)
        return 1

    files = _load_files(args.repo_path, entry)

    try:
        current_value = resolve_current_value(files, locator)
        updated_files = apply_change(files, locator, current_value, args.proposed_value)
    except SEOSiteMappingRequiredError as exc:
        print(f"SITE_MAPPING_REQUIRED: {exc.public_message}", file=sys.stderr)
        return 1

    print(f"Page: {entry.url_path}")
    print(f"Field: {field.value}")
    print(f"Current value: {current_value!r}")
    print(f"Proposed value: {args.proposed_value!r}")
    print()
    for file_path, updated_content in updated_files.items():
        original_content = files[file_path]
        if original_content == updated_content:
            continue
        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            updated_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        sys.stdout.writelines(diff)
    print()
    print("Dry run complete. No git operations performed; no pull request opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
