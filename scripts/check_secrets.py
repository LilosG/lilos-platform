"""Check repository files for non-empty dotenv values and high-confidence secret patterns."""

import re
from collections.abc import Iterable
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPOSITORY_ROOT / ".env.example"
EXCLUDED_DIRECTORY_NAMES = {
    ".astro",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "coverage",
    "dist",
    "node_modules",
}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}


def validate_env_example(path: Path = ENV_EXAMPLE) -> list[str]:
    """Return validation errors for non-empty or malformed environment declarations."""
    errors: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"{path.name}:{line_number}: missing '='")
            continue
        name, value = line.split("=", maxsplit=1)
        if not name or not name.replace("_", "").isalnum() or not name[0].isalpha():
            errors.append(f"{path.name}:{line_number}: invalid variable name")
        if value:
            errors.append(f"{path.name}:{line_number}: example values must be empty")
    return errors


def repository_files(root: Path = REPOSITORY_ROOT) -> Iterable[Path]:
    """Yield small text candidates while excluding generated and dependency directories."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in path.relative_to(root).parts):
            continue
        if path.stat().st_size > 2_000_000:
            continue
        yield path


def find_secret_patterns(root: Path = REPOSITORY_ROOT) -> list[str]:
    """Return file-and-pattern findings without echoing any candidate secret value."""
    findings: list[str] = []
    for path in repository_files(root):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(root)}: matched {label} pattern")
    return findings


def main() -> int:
    """Run the Phase 0 secret checks and return a process-friendly status code."""
    errors = [*validate_env_example(), *find_secret_patterns()]
    if errors:
        print("Repository secret validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Environment values are empty and no high-confidence secret patterns were found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
