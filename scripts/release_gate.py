"""Fail-closed repository acceptance-package gate."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "docs/PHASE-17-ACCEPTANCE.md",
    "docs/PHASE-18-ACCEPTANCE.md",
    "docs/PHASE-19-ACCEPTANCE.md",
    "docs/SECTION-27-ACCEPTANCE.md",
    "docs/PRODUCTION-DEPLOYMENT.md",
    "docs/BACKUP-RESTORE.md",
    "docs/DISASTER-RECOVERY.md",
)


def missing_release_documents(root: Path = ROOT) -> list[str]:
    return [item for item in REQUIRED if not (root / item).is_file()]


def main() -> int:
    missing = missing_release_documents()
    if missing:
        print("release gate blocked: " + ", ".join(missing))
        return 1
    print("release acceptance package is structurally complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
