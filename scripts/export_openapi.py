"""Deterministic public API schema export; no database, secrets or live I/O."""

import argparse
import json
from pathlib import Path

from apps.api.app.config import Settings
from apps.api.app.main import create_app


def export(output: Path) -> None:
    app = create_app(Settings(_env_file=None, internal_admin_routes_enabled=False))  # type: ignore[call-arg]
    schema = app.openapi()
    # Tool and internal surfaces are not browser transport contracts.
    schema["paths"] = {
        key: value
        for key, value in schema["paths"].items()
        if not key.startswith(("/internal", "/api/internal", "/api/v1/hermes"))
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args().output)
