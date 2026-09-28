"""Run deterministic, isolated file-level shards of the complete Python test suite."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests" / "python"


def discover_test_files(test_root: Path = TEST_ROOT) -> tuple[Path, ...]:
    """Match pytest's default test-file patterns under the configured testpaths root."""
    return tuple(
        sorted(
            path.relative_to(test_root.parent.parent)
            for path in test_root.rglob("*.py")
            if path.is_file() and (path.name.startswith("test_") or path.name.endswith("_test.py"))
        )
    )


def partition(files: tuple[Path, ...], shard_count: int) -> tuple[tuple[Path, ...], ...]:
    if shard_count < 1:
        raise ValueError("shard count must be positive")
    if not files:
        raise ValueError("no Python test files discovered")
    if shard_count > len(files):
        raise ValueError("shard count exceeds discovered test-file count")
    return tuple(tuple(files[index::shard_count]) for index in range(shard_count))


def verify_partition(files: tuple[Path, ...], shards: tuple[tuple[Path, ...], ...]) -> None:
    inventory = set(files)
    assigned = [path for shard in shards for path in shard]
    if len(inventory) != len(files):
        raise ValueError("discovered test inventory contains duplicates")
    if set(assigned) != inventory or len(assigned) != len(inventory):
        raise ValueError("shards omit or duplicate test files")
    for left in range(len(shards)):
        for right in range(left + 1, len(shards)):
            if set(shards[left]) & set(shards[right]):
                raise ValueError(f"shards {left} and {right} overlap")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard-count", type=int, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify", action="store_true")
    action.add_argument("--shard-index", type=int)
    args = parser.parse_args()

    try:
        files = discover_test_files()
        shards = partition(files, args.shard_count)
        verify_partition(files, shards)
    except ValueError as exc:
        parser.error(str(exc))

    if args.verify:
        print(f"Discovered {len(files)} Python test files; complete union; zero overlap.")
        for index, shard in enumerate(shards):
            print(f"Shard {index}: {len(shard)} files")
        return 0

    index = args.shard_index
    if index is None or index < 0 or index >= args.shard_count:
        parser.error("shard index must be between 0 and shard count - 1")
    print(f"Running shard {index}: {len(shards[index])} of {len(files)} test files", flush=True)
    return subprocess.call(
        [sys.executable, "-m", "pytest", *(str(path) for path in shards[index])],
        cwd=ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
