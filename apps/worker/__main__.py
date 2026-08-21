"""Production durable-worker process entrypoint."""

import asyncio

import apps.worker.bootstrap  # noqa: F401 — register ORM models before first query
import apps.api.app.execution.operational_extensions  # noqa: F401 — register orchestration handlers
from apps.api.app.execution.runtime import process_main, run_worker


def main() -> int:
    """Run until a termination signal or a fail-closed runtime failure."""
    return asyncio.run(process_main("lilos-worker", run_worker))


if __name__ == "__main__":
    raise SystemExit(main())
