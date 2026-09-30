"""Dry-run a governed site change against a local checkout of a client repository.

Resolves the page through the same page map and resolver the `seo.apply_site_change`
executor uses, reads the mapped files, applies every requested change entirely in
memory, and prints a unified diff of exactly what would change. It never touches
git, never opens a pull request and never writes to the checkout -- it is the
URL -> file -> field proof, run before any PR-writing path is exercised.

    uv run python -m scripts.site_change_dry_run \\
        --repository LilosG/coco-maya \\
        --repo-path /path/to/local/coco-maya \\
        --url-path /brunch \\
        --change seo_title="New SEO title under sixty characters" \\
        --change meta_description="A new meta description under 160 characters."

Exits non-zero if a change does not validate or the page cannot be mapped.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem
from apps.api.app.products.seo.errors import SEOSiteMappingRequiredError
from apps.api.app.products.seo.site_map_resolver import (
    KeystaticJsonLocator,
    SiteMapLocator,
    apply_change,
    page_map_from_contract,
    resolve_current_value,
    resolve_entry,
)
from scripts.seed_publishing_target_contracts import SITE_CHANGE_PREFIXES, full_contract

# A dry run has no page row; the id only satisfies SiteChangeItem's shape.
_DRY_RUN_PAGE_ID = "00000000-0000-0000-0000-000000000000"


def _parse_changes(raw_changes: list[str]) -> dict[SiteChangeField, str]:
    changes: dict[SiteChangeField, str] = {}
    for raw in raw_changes:
        name, separator, value = raw.partition("=")
        if not separator:
            raise SystemExit(f"--change must look like field=value, got {raw!r}")
        try:
            field = SiteChangeField(name)
        except ValueError:
            allowed = ", ".join(f.value for f in SiteChangeField)
            raise SystemExit(f"Unknown field {name!r}; expected one of: {allowed}") from None
        if field in changes:
            raise SystemExit(f"Field {name!r} given more than once")
        changes[field] = value
    return changes


def _encode(locator: SiteMapLocator, value: str) -> str:
    """How `value` is spelled inside the file a locator points at."""
    return (
        json.dumps(value, ensure_ascii=False)
        if isinstance(locator, KeystaticJsonLocator)
        else value
    )


def _load_files(repo_path: Path, locators: list[SiteMapLocator]) -> dict[str, str]:
    files: dict[str, str] = {}
    for locator in locators:
        full_path = repo_path / locator.file_path
        if full_path.is_file():
            files[locator.file_path] = full_path.read_text()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repository", required=True, help="e.g. LilosG/coco-maya")
    parser.add_argument("--repo-path", required=True, type=Path)
    parser.add_argument("--url-path", required=True, help="live page path, e.g. /brunch")
    parser.add_argument("--change", action="append", required=True, metavar="FIELD=VALUE")
    args = parser.parse_args()

    contract = full_contract(args.repository)
    page_map = page_map_from_contract(contract)
    if not page_map:
        print(f"SITE_MAPPING_REQUIRED: no page map recorded for {args.repository}", file=sys.stderr)
        return 1
    changes = _parse_changes(args.change)
    originals: dict[SiteChangeField, str] = {}

    try:
        entry = resolve_entry(page_map, args.url_path, SITE_CHANGE_PREFIXES[args.repository])
        locators: dict[SiteChangeField, SiteMapLocator] = {}
        for field in changes:
            locator = entry.fields.get(field)
            if locator is None:
                raise SEOSiteMappingRequiredError(f"{entry.url_path} has no mapping for {field}.")
            locators[field] = locator

        original = _load_files(args.repo_path, list(locators.values()))
        updated = dict(original)
        for field, proposed in changes.items():
            current = resolve_current_value(updated, locators[field])
            originals[field] = current
            # Same deterministic gate the executor enforces: length bounds, non-empty,
            # and proposed != current.
            SiteChangeItem(
                page_id=_DRY_RUN_PAGE_ID,  # type: ignore[arg-type]
                field=field,
                current_value=current,
                proposed_value=proposed,
                rationale="dry run",
            )
            print(f"{field.value}: {current!r} -> {proposed!r}")
            updated = apply_change(updated, locators[field], current, proposed)
    except SEOSiteMappingRequiredError as exc:
        print(f"SITE_MAPPING_REQUIRED: {exc.public_message}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        first = exc.errors()[0]
        print(f"SITE_CHANGE_INVALID: {first['msg']}", file=sys.stderr)
        return 1

    print()
    changed_files = 0
    for file_path, new_content in updated.items():
        if original[file_path] == new_content:
            continue
        changed_files += 1
        for line in difflib.unified_diff(
            original[file_path].splitlines(),
            new_content.splitlines(),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        ):
            # Minified JSON puts a whole page on one line; the value-level proof
            # below is the real evidence, so keep the line diff readable.
            print(line if len(line) <= 240 else f"{line[:240]}... [{len(line)} chars]")

    # Inverse proof: put each original value back into the updated text. If the edit
    # touched anything besides the approved values, the result differs from the
    # original file and the dry run fails.
    for file_path, new_content in updated.items():
        restored = new_content
        for field, locator in locators.items():
            if locator.file_path != file_path:
                continue
            restored = restored.replace(
                _encode(locator, changes[field]), _encode(locator, originals[field]), 1
            )
        if restored != original[file_path]:
            print(f"FAIL: {file_path} changed outside the approved values.", file=sys.stderr)
            return 1
    print()
    print(
        f"Verified: restoring the {len(changes)} original value(s) reproduces "
        f"{changed_files} file(s) byte for byte -- nothing else changed."
    )
    print()
    print(
        f"Dry run complete: {len(changes)} value(s) across {changed_files} file(s). "
        "No git operations performed; no pull request opened."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
