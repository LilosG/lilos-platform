"""Fail-closed repository acceptance-package and production-release gate."""

import re
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
RELEASE_IDENTITY_SCRIPTS = (
    "scripts/render_start_api.sh",
    "scripts/render_start_worker.sh",
    "scripts/render_start_scheduler.sh",
    "scripts/render_start_hermes.sh",
)
RELEASE_IDENTITY_EXPORT = re.compile(
    r'export\s+LILOS_RELEASE="\$\{RENDER_GIT_COMMIT(?::\?[^}]*)?\}"'
)
PRODUCTION_RENDER_SERVICES = (
    "lilos-hermes",
    "lilos-api",
    "lilos-worker",
    "lilos-scheduler",
)


def missing_release_documents(root: Path = ROOT) -> list[str]:
    return [item for item in REQUIRED if not (root / item).is_file()]


def has_fail_closed_release_identity(content: str) -> bool:
    """Return true when LILOS_RELEASE is derived directly from Render's git SHA."""
    return RELEASE_IDENTITY_EXPORT.search(content) is not None


def release_identity_violations(root: Path = ROOT) -> list[str]:
    violations: list[str] = []
    for relative_path in RELEASE_IDENTITY_SCRIPTS:
        path = root / relative_path
        if not path.is_file():
            violations.append(f"{relative_path}: missing")
            continue
        content = path.read_text(encoding="utf-8")
        if not has_fail_closed_release_identity(content):
            violations.append(
                f"{relative_path}: LILOS_RELEASE must derive directly from RENDER_GIT_COMMIT"
            )
    return violations


def render_release_violations(root: Path = ROOT) -> list[str]:
    path = root / "render.yaml"
    if not path.is_file():
        return ["render.yaml: missing"]
    content = path.read_text(encoding="utf-8")
    violations: list[str] = []
    for service_name in PRODUCTION_RENDER_SERVICES:
        marker = f"  - name: {service_name}\n"
        start = content.find(marker)
        if start < 0:
            violations.append(f"render.yaml: missing {service_name}")
            continue
        next_service = content.find("\n  - name: ", start + len(marker))
        service_block = content[start : next_service if next_service >= 0 else len(content)]
        if "branch: main" not in service_block:
            violations.append(f"render.yaml: {service_name} must deploy from main")
        if "autoDeployTrigger: checksPass" not in service_block:
            violations.append(f"render.yaml: {service_name} must deploy only after checks pass")
    return violations


def main() -> int:
    violations = [
        *missing_release_documents(),
        *release_identity_violations(),
        *render_release_violations(),
    ]
    if violations:
        print("release gate blocked: " + ", ".join(violations))
        return 1
    print(
        "release acceptance package is structurally complete; production services "
        "share a fail-closed repository release identity and checks-pass deploy contract"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
