"""Regenerate in isolation and compare committed transport artifacts byte-for-byte."""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.export_openapi import export

ROOT = Path(__file__).resolve().parents[1]


def check() -> None:
    with TemporaryDirectory() as temporary:
        schema = Path(temporary) / "openapi.json"
        types = Path(temporary) / "api.ts"
        export(schema)
        subprocess.run(
            [str(ROOT / "node_modules/.bin/openapi-typescript"), str(schema), "-o", str(types)],
            check=True,
        )
        for actual, expected in (
            (schema, ROOT / "packages/contracts/openapi.json"),
            (types, ROOT / "packages/contracts/src/generated/api.ts"),
        ):
            if not expected.exists() or actual.read_bytes() != expected.read_bytes():
                raise SystemExit(f"Transport artifact drift: {expected.relative_to(ROOT)}")
    print("OpenAPI and generated TypeScript are current")


if __name__ == "__main__":
    check()
